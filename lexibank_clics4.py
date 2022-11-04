import pathlib
import collections

import pycldf
from pylexibank.dataset import CLDFSpec
from pylexibank.cldf import LexibankWriter
from pylexibank import Dataset as BaseDataset
from cltoolkit import Wordlist
from git import Repo
from clldutils.misc import slug

from pylexibank import Concept, Lexeme, Language, progressbar
import attr

LANGUAGES = 250

@attr.s
class CustomConcept(Concept):
    Tag = attr.ib(default=None)


@attr.s
class CustomLexeme(Lexeme):
    ConceptInSource = attr.ib(default=None)

@attr.s
class CustomLanguage(Language):
    Concept_Count = attr.ib(default=None, metadata={"format": "integer"})
    Form_Count = attr.ib(default=None, metadata={"format": "integer"})


class Dataset(BaseDataset):
    dir = pathlib.Path(__file__).parent
    id = "clicsbp"
    concept_class = CustomConcept
    lexeme_class = CustomLexeme
    language_class = CustomLanguage

    def cldf_specs(self):  # A dataset must declare all CLDF sets it creates.
        return CLDFSpec(
            dir=self.cldf_dir,
            writer_cls=LexibankWriter,
            module='Wordlist',
            data_fnames=dict(
                LanguageTable="languages.csv",
                ParameterTable='parameters.csv',
                CognateTable="cognates.csv",
                FormTable='forms.csv',
            ),
            zipped=['FormTable'],
        )

    def cmd_download(self, args):
        for dataset in self.etc_dir.read_csv(
                "datasets.tsv", delimiter="\t",
                dicts=True):
            if self.raw_dir.joinpath(
                    dataset["ID"], "cldf", "cldf-metadata.json").exists():
                args.log.info("skipping {0}".format(dataset["ID"]))
            else:
                args.log.info("cloning {0} to raw/{0}".format(dataset["ID"]))
                Repo.clone_from(
                 "https://github.com/"+
                 dataset["Organisation"]+"/"+
                 dataset["Repository"]+'.git',
                 self.raw_dir / dataset["ID"])
        
    def cmd_makecldf(self, args):

        datasets = [pycldf.Dataset.from_metadata(
            self.raw_dir / ds["ID"] / "cldf/cldf-metadata.json") for ds in
            self.etc_dir.read_csv("datasets.tsv", delimiter="\t",
                dicts=True)]
        args.log.info("loaded datasets")
        wl = Wordlist(datasets, ts=args.clts.api.bipa)

        # sort the concepts by number of unique glottocodes
        all_concepts = sorted(
                wl.concepts,
                key=lambda x: len(set([form.language.glottocode for form in
                    x.forms_with_sounds])),
                reverse=True)
        with open(
                self.etc_dir.joinpath("concepts.tsv"), 
                "w") as f:
            f.write("ID\tGLOSS\tFREQUENCY\n")
            for concept in all_concepts:
                if concept.id:
                    f.write("\t".join([
                            concept.concepticon_id, 
                            concept.concepticon_gloss,
                            str(len(set([form.language.glottocode for form in
                                concept.forms_with_sounds])))])+"\n")
        args.log.info("wrote concepts to file")
        input("bis hier")
        unmerge = collections.defaultdict(set)
        for concept in self.concepts:
            for gloss in concept["BROADER_CONCEPT"].split(" // "):
                unmerge[gloss].add(concept["CONCEPTICON_GLOSS"])

        selected_concepts = [concept.id for concept in all_concepts if
                concept.id not in unmerge][:1500]

        # get valid languages
        valid_languages = []
        visited = set()
        for language in sorted(
                wl.languages,
                key=lambda x: len([c for c in x.concepts if c.id in
                    selected_concepts]),
                reverse=True):
            if language.glottocode in visited:
                pass
            else:
                cov = sum([
                    len(unmerge.get(c.id, [""])) for c in language.concepts if c.id in unmerge or \
                                c.id in selected_concepts]) 
                if language.latitude and cov >= LANGUAGES:
                    visited.add(language.glottocode)
                    valid_languages.append(language.id)

        args.log.info("found {0} valid languages".format(len(valid_languages)))

        concepts = {concept["CONCEPTICON_GLOSS"]: concept["TAG"] for concept in
                self.concepts}
                        
        for concept in self.concepts:
            if concept["CONCEPTICON_GLOSS"] in selected_concepts:
                args.writer.add_concept(
                        ID=slug(concept["CONCEPTICON_GLOSS"], lowercase=False),
                        Name=concept["ENGLISH"],
                        Concepticon_ID=concept["CONCEPTICON_ID"],
                        Concepticon_Gloss=concept["CONCEPTICON_GLOSS"],
                        Tag=concept["TAG"]
                        )
        args.log.info("added concepts")
        
        new_concepts = {}
        clics = []
        accepted_languages = []
        for language in wl.languages:
            if (language.glottocode and
                    language.id in valid_languages):
                args.log.info("Processing {0}".format(language.id))
                cnc_count, frm_count = 0, 0
                for form in language.forms_with_sounds:
                    if (form.concept and form.concept.concepticon_gloss in
                            concepts and form.concept.concepticon_gloss in
                            selected_concepts):
                        clics += [[
                                language.id,
                                form.id,
                                form.concept.id, 
                                form.value,
                                form.form,
                                form.sounds,
                                language.family,
                                ""
                                ]]
                        cnc_count += 1
                        frm_count += 1
                    elif (form.concept and form.concept.concepticon_gloss in
                            unmerge):
                        for gloss in unmerge[form.concept.concepticon_gloss]:
                            if gloss in selected_concepts:
                                clics += [[
                                        language.id,
                                        form.id,
                                        gloss,
                                        form.value,
                                        form.form,
                                        form.sounds,
                                        language.family,
                                        form.concept.id]]
                                cnc_count += 1
                                frm_count += 1
                    elif (form.concept and form.concept.concepticon_gloss in
                            selected_concepts):
                        clics += [[
                                language.id,
                                form.id,
                                form.concept.id,
                                form.value,
                                form.form,
                                form.sounds,
                                language.family,
                                ""
                                ]]
                        cnc_count += 1
                        frm_count += 1
                        if form.concept.name not in new_concepts:
                            new_concepts[form.concept.name] = form.concept
                args.writer.add_language(
                        ID=language.id,
                        Name=language.name,
                        Family=language.family,
                        Latitude=language.latitude,
                        Longitude=language.longitude,
                        Glottocode=language.glottocode,
                        Concept_Count=cnc_count,
                        Form_Count=frm_count
                        )
                accepted_languages += [language.id]
                args.log.info("... added {0} with {1} concepts".format(language.id, cnc_count))


        # add remaining concepts
        for concept in new_concepts.values():
            args.writer.add_concept(
                    ID=slug(concept.concepticon_gloss, lowercase=False),
                    Name=concept.name,
                    Concepticon_ID=concept.concepticon_id,
                    Concepticon_Gloss=concept.concepticon_gloss,
                    Tag=""
                    )
            concepts[concept.concepticon_gloss] = ""
        args.log.info("added remaining concepts")

        for lng_id, frm_id, cnc_id, frm_val, frm_frm, frm_snd, _, cnc_is in progressbar(
                clics, desc="adding forms"):
            args.writer.add_form_with_segments(
                    Local_ID=frm_id,
                    Parameter_ID=slug(cnc_id, lowercase=False),
                    Language_ID=lng_id,
                    Value=frm_val,
                    Form=frm_frm,
                    Segments=frm_snd,
                    ConceptInSource=cnc_is
                    )

        # add info on coverage
        coverage = collections.defaultdict(dict)
        perfamily = collections.defaultdict(lambda :
                collections.defaultdict(list))
        poweran = {concept.id: {language: 0 for language in accepted_languages} for concept
                in all_concepts}
        families = set()
        for language, _, concept, _, _, _, family, _ in clics:
            coverage[concept][language] = family
            perfamily[concept][family] += [language]
            poweran[concept][language] = 1
            families.add(family)

        with open(self.dir / "output" / "power_analysis.tsv", "w") as f:
            for concept in coverage:
                for language in coverage[concept]:
                    f.write("{0}\t{1}\t{2}\t{3}\t{4}\n".format(
                        concept,
                        concepts.get(concept, ""),
                        wl.languages[language].family,
                        language,
                        poweran[concept][language]))

        with open(self.dir / "output" / "coverage.tsv", "w") as f:
            f.write("Concept\tTag\tLanguages\tFamilies\n")
            for k, vals in coverage.items():
                f.write("{0}\t{1}\t{2}\t{3}\n".format(
                    k, concepts[k], len(vals), len(set(vals.values()))))

        # make big coverage map 
        with open(self.dir / "output" / "coverage-per-family.tsv", "w") as f:
            f.write("Concept\tTag")
            for fam in sorted(families):
                f.write("\t"+fam)
            f.write("\n")
            for concept in perfamily:
                f.write("{0}\t{1}".format(concept, concepts[concept]))
                for fam in families:
                    f.write("\t{0}".format(len(set(perfamily[concept][fam]))))
                f.write("\n")







