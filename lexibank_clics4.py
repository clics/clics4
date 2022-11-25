"""Lexibank Script for CLICS⁴"""
import pathlib

import networkx as nx
import pycldf
from pylexibank.dataset import CLDFSpec as LexibankSpec
from cldfbench import CLDFSpec as CldfBenchSpec
from pylexibank.cldf import LexibankWriter
from pylexibank import Dataset as BaseDataset
from cltoolkit import Wordlist
from git import Repo
from clldutils.misc import slug
from lingpy.convert.graph import networkx2igraph
import itertools

from pyclics.colexifications import (
    get_colexifications, get_transition_matrix, normalize_weights)
from pyclics.util import write_gml

from pylexibank import Concept, Lexeme, Language, progressbar
import attr

LANGUAGES = 250
WRITE_CONCEPTS = False
RERUN = False


@attr.s
class CustomConcept(Concept):
    OriginalConcept = attr.ib(default=True)


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
            ),
            "generic": CldfBenchSpec(
                dir=self.cldf_dir,
                metadata_fname="cldf-metadata.json",
                module='Generic',
                data_fnames=dict(
                    ParameterTable='concepts.csv',
                ),
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
        # concepticongloss 2 id
        gloss2id = {
            concept.gloss: concept.id for concept in
            self.concepticon.conceptsets.values()}
        args.log.info("created concepticon gloss to ID converter")

        if RERUN:
            with self.cldf_writer(args) as writer:

                datasets = [pycldf.Dataset.from_metadata(
                    self.raw_dir / ds["ID"] / "cldf/cldf-metadata.json") for ds in
                               self.etc_dir.read_csv(
                                   "datasets.tsv", delimiter="\t",
                                   dicts=True)] # DEBUGGING
                args.log.info("loaded datasets")
                wl: Wordlist = Wordlist(datasets, ts=args.clts.api.bipa)
            
                # read target concepts
                targets, sources = {}, {}
                for row in self.etc_dir.read_csv(
                        "concept-modifications.tsv",
                        delimiter="\t", dicts=True):
                    if row["Status"].strip() in ["edited", "accepted"]:
                        targets[row["Source"]] = row["Targets"].split(" // ")
                        for t in row["Targets"].split(" // "):
                            sources[t] = row["Source"]
            
                # sort the concepts by number of unique glottocodes
                all_concepts = sorted(
                    wl.concepts,
                    key=lambda x: len(set([form.language.glottocode for form in
                                           x.forms_with_sounds])),
                    reverse=True)
                # write concept down if needed
                if WRITE_CONCEPTS:
                    with open(
                            self.etc_dir.joinpath("concepts.tsv"),
                            "w") as f:
                        f.write("ID\tGLOSS\tFREQUENCY\n")
                        for concept in all_concepts:
                            if concept.id and concept.concepticon_id:
                                f.write("\t".join([
                                    concept.concepticon_id,
                                    concept.concepticon_gloss,
                                    str(len(set([form.language.glottocode for form in
                                                 concept.forms_with_sounds])))]) + "\n")
                    args.log.info("wrote concept frequencies to file")
            
                # check for duplicates in the selected concepts
                selected_concepts, visited = [], set()
                for concept in all_concepts:
                    if concept.id in visited:
                        continue
                    if concept.id in targets:
                        selected_concepts.extend(targets[concept.id])
                        for t in targets[concept.id]:
                            visited.add(t)
                    else:
                        if concept.id not in gloss2id:
                            args.log.info("Concepticon 3-Problem {0}".format(concept.id))
                        else:
                            selected_concepts.append(concept.id)
                            visited.add(concept.id)
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
                        if (form.concept and form.concept.id in selected_concepts):
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
                        elif (form.concept and form.concept.id in targets):
                            for gloss in targets[form.concept.id]:
                                if gloss in selected_concepts:
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
                missing = set()
                for (
                        language_id,
                        form_id,
                        concept_id,
                        form_val,
                        form_form,
                        form_sounds,
                        concept_in_source
                ) in progressbar(clics, desc="adding forms"):
                    if concept_id in selected_concepts:
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
                    else:
                        missing.add((concept_id, language_id))
                language_table = writer.cldf["LanguageTable"]
                for m, lng in missing:
                    args.log.info("Missing concept {0} / {1}".format(m, lng))

        with self.cldf_writer(args, cldf_spec="structure", clean=False) as writer:
            writer.cldf.add_component(language_table)
            writer.cldf.add_columns(
                "ParameterTable",
                {"name": "Source", "datatype": "string"},
                {"name": "Target", "datatype": "string"},
                {"name": "Form_Count", "datatype": "integer"},
                {"name": "Variety_Count", "datatype": "integer"},
                {"name": "Language_Count", "datatype": "integer"},
                {"name": "Family_Count", "datatype": "integer"},
                {"name": "Variety_Weight", "datateype": "float"},
                {"name": "Language_Weight", "datateype": "float"},
                {"name": "Family_Weight", "datateype": "float"},
                {"name": "Forms", "datatype": {"base": "string"}, "separator": " "},
                {"name": "Varieties", "datatype": {"base": "string"}, "separator": " "},
                {"name": "Languages", "datatype": {"base": "string"}, "separator": " "},
                {"name": "Families", "datatype": {"base": "string"}, "separator": " "},
                {"name": "Missing_Data", "datatype": {"base": "string"}, "separator": " "}
            )
            col = writer.cldf.add_table("concepts.csv")
            writer.cldf.add_columns(
                "concepts.csv",
                {
                    "name": "Concepticon_ID",
                    "datatype": "string",
                    "propertyUrl": "http://cldf.clld.org/v1.0/terms.rdf#concepticonReference"
                 },
                {
                    "name": "Concepticon_Gloss",
                    "datatype": "string",
                },
                {"name": "Form_Count", "datatype": "integer"},
                {"name": "Variety_Count", "datatype": "integer"},
                {"name": "Language_Count", "datatype": "integer"},
                {"name": "Family_Count", "datatype": "integer"},
                {"name": "Community", "datatype": "string", "null": "?"},
                {"name": "CentralConcept", "datatype": "string", "null": "?"},
                {"name": "Forms", "datatype": {"base": "string", "separator": " "}},
                {"name": "Varieties", "datatype": {"base": "string"}, "separator": " "},
                {"name": "Languages", "datatype": {"base": "string"}, "separator": " "},
                {"name": "Families", "datatype": {"base": "string"}, "separator": " "},
                {"name": "Similarities", "datatype": "json"},
            )
            col.tableSchema.primaryKey = ["Concepticon_ID"]

            wl = Wordlist(
                [pycldf.Dataset.from_metadata(self.cldf_dir.joinpath("Wordlist-metadata.json"))],
                ts=args.clts.api.bipa
            )
            graph = get_colexifications(wl)
            for w in ["form", "variety", "language", "family"]:
                normalize_weights(graph, w+"_weight", w+"_count", w+"_count")
            ig = networkx2igraph(graph)
            communities = ig.community_infomap(edge_weights="family_weight", vertex_weights="family_count")
            community_labels = {}
            for i, nodes_ in enumerate(communities):
                nodes = [ig.vs[node]["Name"] for node in nodes_]
                central_node = sorted(
                    nx.degree(graph, nodes, weight="family_weight"),
                    key=lambda x: x[1],
                    reverse=True)[0][0]
                for node in nodes:
                    community_labels[node] = (str(i+1), central_node)
                    graph.nodes[node]["community"] = str(i+1)
                    graph.nodes[node]["central_concept"] = central_node

            write_gml(graph, self.cldf_dir.joinpath("clics4-graph.gml"))
            args.log.info("computed colexifications")

            for nodeA, nodeB, data in progressbar(
                    graph.edges(data=True),
                    desc="writing colexifications"):
                idx = "{0}-colexifies-{1}".format(
                    slug(nodeA, lowercase=True),
                    slug(nodeB, lowercase=True)
                )
                # compute missing data
                missing_data = []
                for language in wl.languages:
                    if language.id not in data["languages"]:
                        if not nodeA in language.concepts or not nodeB in language.concepts:
                            missing_data.append(language.id)

                writer.objects["ParameterTable"].append(
                    {
                        "ID": idx,
                        "Source": nodeA,
                        "Target": nodeB,
                        "Variety_Count": data["variety_count"],
                        "Language_Count": data["language_count"],
                        "Family_Count": data["family_count"],
                        "Variety_Weight": data["variety_weight"],
                        "Language_Weight": data["language_weight"],
                        "Family_Weight": data["family_weight"],
                        "Forms": data["forms"],
                        "Varieties": data["varieties"],
                        "Languages": data["languages"],
                        "Families": data["families"],
                        "Missing_Data": missing_data
                    }
                )
                for language_id in data["varieties"]:
                    writer.objects["ValueTable"].append(
                        {
                            "ID": idx + "-" + language_id,
                            "ParameterID": idx,
                            "Language_ID": language_id,
                            "Value": 1
                        }
                    )

            # extend graph by adding missing edges
            for nodeA, nodeB in itertools.combinations(list(graph.nodes), r=2):
                if not nodeB in graph[nodeA]:
                    graph.add_edge(nodeA, nodeB, family_weight=1/100000)
            transition_matrix, node_list, _ = get_transition_matrix(
                graph, steps=10, weight="family_weight", normalize=True
            )
            args.log.info("computed similarity matrix")
            # compute pairwise concept similarities based on random walks
            similarities = {}
            for i, nodeA in enumerate(node_list):
                similarities[nodeA] = {}
                for j, nodeB in enumerate(node_list):
                    if transition_matrix[i][j] >= 0.001:
                        similarities[nodeA][nodeB] = transition_matrix[i][j]
            for concept in map(lambda x: x.id, wl.concepts):
                if concept not in community_labels:
                    args.log.info("Concept {0} withouth community.".format(concept))
                writer.objects["concepts.csv"].append(
                    {
                        "Concepticon_ID": gloss2id[concept],
                        "Concepticon_Gloss": concept,
                        "Form_Count": graph.nodes[concept]["form_count"],
                        "Variety_Count": graph.nodes[concept]["variety_count"],
                        "Language_Count": graph.nodes[concept]["language_count"],
                        "Family_Count": graph.nodes[concept]["family_count"],
                        "Community": community_labels[concept][0],
                        "CentralConcept": community_labels[concept][1],
                        "Similarities": similarities.get(concept, {}),
                        "Forms": graph.nodes[concept]["forms"],
                        "Varieties": graph.nodes[concept]["varieties"],
                        "Languages": graph.nodes[concept]["languages"],
                        "Families": graph.nodes[concept]["families"]
                    }
                )





