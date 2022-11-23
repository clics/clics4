"""Lexibank Script for CLICS⁴"""
import pathlib

import pycldf
from pylexibank.dataset import CLDFSpec as LexibankSpec
from cldfbench import CLDFSpec as CldfBenchSpec
from pylexibank.cldf import LexibankWriter
from pylexibank import Dataset as BaseDataset
from cltoolkit import Wordlist
from git import Repo
from clldutils.misc import slug
import itertools

from pyclics.colexifications import get_colexifications, weight_by_cognacy, get_transition_matrix
from pyclics.util import write_gml

from pylexibank import Concept, Lexeme, Language, progressbar
import attr

LANGUAGES = 250


@attr.s
class CustomConcept(Concept):
    OriginalConcept = attr.ib(default=True)
    Variety_Count = attr.ib(default=None, metadata={"format": "integer"})
    Language_Count = attr.ib(default=None, metadata={"format": "integer"})
    Family_Count = attr.ib(default=None, metadata={"format": "integer"})
    Community = attr.ib(default=None, metadata={"format": "integer"})

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
        return {
            None: LexibankSpec(
                dir=self.cldf_dir,
                writer_cls=LexibankWriter,
                module='Wordlist',
                data_fnames=dict(
                    LanguageTable="languages.csv",
                    ParameterTable='parameters.csv',
                    CognateTable="cognates.csv",
                    FormTable='forms.csv',
                ),
                zipped=['FormTable']),
            "structure": CldfBenchSpec(
                module="StructureDataset",
                dir=self.cldf_dir,
                data_fnames={"ParameterTable": "colexifications.csv"},
                zipped=["ParameterTable", "ValueTable"]
            )
        }

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
                    "https://github.com/" +
                    dataset["Organisation"] + "/" +
                    dataset["Repository"] + '.git',
                    self.raw_dir / dataset["ID"])

    def cmd_makecldf(self, args):
        with self.cldf_writer(args) as writer:

            # concepticongloss 2 id
            gloss2id = {
                concept.gloss: concept.id for concept in
                self.concepticon.conceptsets.values()}
            args.log.info("created concepticon gloss to ID converter")
            datasets = [pycldf.Dataset.from_metadata(
                self.raw_dir / ds["ID"] / "cldf/cldf-metadata.json") for ds in
                           self.etc_dir.read_csv(
                               "datasets.tsv", delimiter="\t",
                               dicts=True)][:4]  # DEBUGGING
            args.log.info("loaded datasets")
            wl = Wordlist(datasets, ts=args.clts.api.bipa)

            # read target concepts
            targets, sources = {}, {}
            for row in self.etc_dir.read_csv(
                    "concept-modifications.tsv",
                    delimiter="\t", dicts=True):
                if row["Status"] in ["edited", "accepted"]:
                    targets[row["Source"]] = row["Targets"].split(" // ")
                    for t in row["Targets"].split(" // "):
                        sources[t] = row["Source"]

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
                                         concept.forms_with_sounds])))]) + "\n")
            args.log.info("wrote concept frequencies to file")

            selected_concepts = []
            for concept in all_concepts:
                if concept.id in targets:
                    selected_concepts.extend(targets[concept.id])
                else:
                    selected_concepts.append(concept.id)
            selected_concepts = selected_concepts[:1500]
            concept_count = {}
            for concept in all_concepts:
                if concept.id in selected_concepts:
                    concept_count[concept.id] = 1
                elif concept.id in targets:
                    if [c for c in targets[concept.id] if c in selected_concepts]:
                        concept_count[concept.id] = 0
                        for t in targets[concept.id]:
                            if t in selected_concepts:
                                concept_count[concept.id] += 1
            args.log.info(
                "calculated frequencies for split concepts ({0}/{1})".format(
                    len(concept_count), sum(concept_count.values()))
            )

            # get valid languages
            valid_language_ids, valid_language_objects, visited = [], [], set()
            for language in sorted(
                    wl.languages,
                    key=lambda x: sum([concept_count[c.id] for c in x.concepts if c.id in
                                                                                  concept_count]),
                    reverse=True
            ):
                if language.glottocode in visited:
                    pass
                else:
                    cov = sum([concept_count[c.id] for c in language.concepts if
                               c.id in concept_count])
                    if language.latitude and language.glottocode and cov >= LANGUAGES:
                        visited.add(language.glottocode)
                        valid_language_ids.append(language.id)
                        valid_language_objects.append(language)
            args.log.info("found {0} valid languages".format(len(valid_language_ids)))
            for concept in selected_concepts:
                writer.add_concept(
                    ID=slug(concept, lowercase=True),
                    Name=concept,
                    Concepticon_ID=gloss2id[concept],
                    Concepticon_Gloss=concept,
                    OriginalConcept=sources.get(concept, "")
                )
            clics, accepted_languages = [], []
            for language in progressbar(valid_language_objects, desc="retrieve forms"):
                cnc_count, frm_count = 0, 0
                for form in language.forms_with_sounds:
                    if (form.concept and form.concept.concepticon_gloss in selected_concepts):
                        clics += [[
                            language.id,
                            form.id,
                            form.concept.id,
                            form.value,
                            form.form,
                            form.sounds,
                            ""
                        ]]
                        cnc_count += 1
                        frm_count += 1
                    elif (form.concept and form.concept.concepticon_gloss in targets):
                        for gloss in targets[form.concept.concepticon_gloss]:
                            clics += [[
                                language.id,
                                form.id,
                                gloss,
                                form.value,
                                form.form,
                                form.sounds,
                                form.concept.id]]
                            cnc_count += 1
                            frm_count += 1
                writer.add_language(
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

            for (
                    language_id,
                    form_id,
                    concept_id,
                    form_val,
                    form_form,
                    form_sounds,
                    concept_in_source
            ) in progressbar(clics, desc="adding forms"):
                writer.add_form_with_segments(
                    Local_ID=form_id,
                    Parameter_ID=slug(concept_id, lowercase=True),
                    Language_ID=language_id,
                    Value=form_val,
                    Form=form_form,
                    Segments=form_sounds,
                    ConceptInSource=concept_in_source,
                    Source=""
                )
            language_table = writer.cldf["LanguageTable"]
        with self.cldf_writer(args, cldf_spec="structure", clean=False) as writer:
            wl = Wordlist(
                [pycldf.Dataset.from_metadata(self.cldf_dir.joinpath("Wordlist-metadata.json"))],
                ts=args.clts.api.bipa
            )
            graph = get_colexifications(wl)
            weight_by_cognacy(graph, 0.45, label="cognate_count")
            transition_matrix, node_list, _ = get_transition_matrix(
                graph, steps=10, weight="family_count", normalize=True
            )
            write_gml(graph, self.cldf_dir.joinpath("clics4-graph.gml"))
            args.log.info("computed colexifications")
            writer.cldf.add_component(language_table)
            writer.cldf.add_columns(
                "ParameterTable",
                {"name": "Source", "datatype": "string"},
                {"name": "Target", "datatype": "string"},
                {"name": "Variety_Count", "datatype": "integer"},
                {"name": "Language_Count", "datatype": "integer"},
                {"name": "Family_Count", "datatype": "integer"},
                {"name": "Cognate_Count", "datateype": "integer"},
                {"name": "Similarity", "datatype": "float"}
                # {"name": "Variety_Weight", "datatype": "float"},
                # {"name": "Language_Weight", "datatype": "float"},
                # {"name": "Family_Weight", "datatype": "float"},
            )
            writer.cldf.add_columns(
                "ValueTable",
                {"name": "SourceWord", "datatype": "string"},
                {"name": "TargetWord", "datatype": "string"},
            )

            for nodeA, nodeB in itertools.combinations(graph.nodes, r=2):
                idx = "{0}-interactswith-{1}".format(slug(nodeA, lowercase=True), slug(nodeB, lowercase=True))
                obj = {
                    "ID": idx,
                    "Source": nodeA,
                    "Target": nodeB,
                    "Variety_Count": 0,
                    "Language_Count": 0,
                    "Family_Count": 0,
                    "Cognate_Count": 0,
                    "Similarity": 0.0
                }
                try:
                    data = graph[nodeA][nodeB]
                except KeyError:
                    data = {}
                for c in ["Variety_Count", "Language_Count", "Family_Count", "Cognate_Count"]:
                    obj[c] = data.get(c.lower(), 0)
                if nodeA in node_list and nodeB in node_list:
                    obj["Similarity"] = transition_matrix[node_list.index(nodeA)][node_list.index(nodeB)]
                writer.objects["ParameterTable"].append(obj)
                for language_id in data.get("varieties", []):
                    writer.objects["ValueTable"].append(
                        {
                            "ID": idx + "-" + language_id,
                            "ParameterID": idx,
                            "Language_ID": language_id,
                            "Value": 1
                        }
                    )
                # get the missing values
                for language in wl.languages:
                    if language.id not in data.get("varieties", []):
                        if nodeA in language.concepts and nodeB in language.concepts:
                            writer.objects["ValueTable"].append(
                                {
                                    "ID": idx + "-" + language.id,
                                    "ParameterID": idx,
                                    "Language_ID": language.id,
                                    "Value": 0
                                }
                            )


            #for nodeA, nodeB, data in progressbar(graph.edges(data=True), desc="writing colexifications"):
            #    idx = "{0}-colexifies-{1}".format(slug(nodeA, lowercase=True), slug(nodeB, lowercase=True))
            #    writer.objects["ParameterTable"].append(
            #        {
            #            "ID": idx,
            #            "Source": nodeA,
            #            "Target": nodeB,
            #            "Variety_Count": data["variety_count"],
            #            "Language_Count": data["language_count"],
            #            "Family_Count": data["family_count"],
            #            "Cognate_Count": data["cognate_count"]
            #        }
            #    )
            #    for language_id in data["varieties"]:
            #        writer.objects["ValueTable"].append(
            #            {
            #                "ID": idx + "-" + language_id,
            #                "ParameterID": idx,
            #                "Language_ID": language_id,
            #                "Value": 1
            #            }
            #        )
            #    # get the missing values
            #    for language in wl.languages:
            #        if language.id not in data["varieties"]:
            #            if nodeA in language.concepts and nodeB in language.concepts:
            #                writer.objects["ValueTable"].append(
            #                    {
            #                        "ID": idx + "-" + language.id,
            #                        "ParameterID": idx,
            #                        "Language_ID": language.id,
            #                        "Value": 0
            #                    }
            #                )
