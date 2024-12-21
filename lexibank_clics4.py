"""Lexibank Script for CLICS⁴"""
import pathlib

import networkx as nx
import pycldf
import pylexibank.dataset
from cldfbench import CLDFSpec as CldfBenchSpec
from pylexibank.cldf import LexibankWriter
from pylexibank import Dataset as BaseDataset
from cltoolkit import Wordlist
from git import Repo
from clldutils.misc import slug
from lingpy.convert.graph import networkx2igraph
import itertools
import zipfile
import json
import codecs
from datetime import datetime
from csvw.dsv import UnicodeWriter
from zenodo_client import Zenodo


from pyclics.colexifications import (
    get_colexifications, get_transition_matrix, normalize_weights)
import pyclics.util

from pylexibank import Concept, Lexeme, Language, progressbar
import attr


CONCEPTS_PER_LANGUAGE_THRESHOLD = 180
CONCEPT_THRESHOLD = 1800
WRITE_CONCEPTS = False
RERUN = True
SUBGRAPH_THRESHOLD = 3
DATASETS =75
MINIMAL_SIMILARITY = 0.01
COLEXIFICATION_THRESHOLD = 2
UPDATE_DATASETS = False
WITH_TOKEN = False


@attr.s
class CustomConcept(Concept):
    Original_Concept = attr.ib(default=None)
    Form_Count = attr.ib(default=None, metadata={"format": "integer"})
    Variety_Count = attr.ib(default=None, metadata={"format": "integer"})
    Language_Count = attr.ib(default=None, metadata={"format": "integer"})
    Family_Count = attr.ib(default=None, metadata={"format": "integer"})
    Community = attr.ib(default=None, metadata={"format": "string"})
    CentralConcept = attr.ib(default=None, metadata={"format": "string"})
    Forms = attr.ib(default=None, metadata={"format": "string", "separator": " "})
    Varieties = attr.ib(default=None, metadata={"format": "string", "separator": " "})
    Languages = attr.ib(default=None, metadata={"format": "string", "separator": " "})
    Families = attr.ib(default=None, metadata={"format": "string", "separator": " // "})
    Neighbors = attr.ib(default=None, metadata={"format": "string", "separator": " // "})
    Similarities = attr.ib(default=None, metadata={"format": "json"})


@attr.s
class CustomLexeme(Lexeme):
    ConceptInSource = attr.ib(default=None)


@attr.s
class CustomLanguage(Language):
    Concept_Count = attr.ib(default=None, metadata={"format": "integer"})
    Form_Count = attr.ib(default=None, metadata={"format": "integer"})
    Contribution_ID = attr.ib(
        default=None,
        metadata={
            "format": "string",
            "propertyUrl": "http://cldf.clld.org/v1.0/terms.rdf#contributionReference"
        })
    Family_Name = attr.ib(default=None)


class Dataset(BaseDataset):
    dir = pathlib.Path(__file__).parent
    id = "clics4"
    concept_class = CustomConcept
    lexeme_class = CustomLexeme
    language_class = CustomLanguage

    def cldf_specs(self):  # A dataset must declare all CLDF sets it creates.
        return {
            None: pylexibank.dataset.CLDFSpec(
                dir=self.cldf_dir,
                writer_cls=LexibankWriter,
                module='Wordlist',
                data_fnames=dict(
                    LanguageTable="languages.csv",
                    ParameterTable='concepts.csv',
                    CognateTable="cognates.csv",
                    FormTable='forms.csv',
                ),
                zipped=["FormTable", "ParameterTable"]),
            "structure": CldfBenchSpec(
                module="StructureDataset",
                dir=self.cldf_dir,
                data_fnames={"ParameterTable": "colexifications.csv"},
                zipped=["ParameterTable", "ValueTable", "concepts.csv"]
            )
        }

    def cmd_download(self, args):
        # TODO: add the sources.bib, using the Zenodo API (pyzenodo3) that allows to retrieve data by DOI
        sources = []
        base_info = []

        if WITH_TOKEN:
            zenodo = Zenodox()
        datasets = []
        for dataset in self.etc_dir.read_csv(
                "datasets.tsv", delimiter="\t",
                dicts=True):
            # get updated version via zenodo
            args.log.info("Processing dataset {0}".format(dataset["ID"]))
            if WITH_TOKEN:
                if dataset["Zenodo"]:
                    did = dataset["Zenodo"].split(".")[2]
                    rec = zenodo.get_record(did)
                    pid = rec.json()["metadata"]["relations"]["version"][0]["parent"]["pid_value"]
                    prec = zenodo.get_record(pid)
                    last_version = prec.json()["metadata"]["version"]
                    last_doi = prec.json()["metadata"]["doi"]
                    if last_version != dataset["Version"]:
                        args.log.warn("Version {0} is not the same as {1} for {2}".format(
                            dataset["version"],
                            last_version,
                            dataset["ID"]))
                        dataset["version"] = last_version
                    if last_doi != dataset["Zenodo"]:
                        args.log.warn("Zenodo DOI for {0} should be {1}".format(
                            dataset["ID"],
                            last_doi))
                        dataset["Zenodo"] = last_doi

                else:
                    args.log.warn("No DOI found for dataset {0}".format(dataset["ID"]))


            if self.raw_dir.joinpath(
                    dataset["ID"], "cldf", "cldf-metadata.json").exists():
                args.log.info("skipping {0}".format(dataset["ID"]))
            else:
                args.log.info("cloning {0} to raw/{0}".format(dataset["ID"]))
                repo = Repo.clone_from(
                    "https://github.com/" +
                    dataset["Organisation"] + "/" +
                    dataset["Repository"] + '.git',
                    self.raw_dir / dataset["ID"])
            repo = Repo(self.raw_dir / dataset["ID"])
            if dataset["Version"]:
                repo.head.set_reference(repo.tags[dataset["Version"]].commit)
            # get metadata to write the reference in standardized form
            with codecs.open(
                    self.raw_dir / dataset["ID"] / ".zenodo.json",
                    "r", 
                    "utf-8") as f:
                meta = json.load(f)
            bibtex = "@book{" + dataset["ID"] + ",\n"
            bibtex += "  author = {" + " AND ".join(
                    [c["name"] for c in meta["creators"]]) + "},\n"
            bibtex += "  editor = {" + " AND ".join(
                    [c["name"] for c in meta["contributors"] if \
                            c["type"] == "Editor"]) + "},\n"
            bibtex += "  title = {" + meta["title"] + "},\n"
            bibtex += "  version = {" + dataset["Version"] + "},\n"
            try:
                bibtex += "  _reference = {" + meta["description"].split("\n")[3][3:-4] + "},\n"
            except KeyError:
                args.log.warn("Description missing for dataset {0}".format(dataset["ID"]))
            bibtex += "  year = {" + str(
                    datetime.fromtimestamp(
                        repo.tags[dataset["Version"]].commit.authored_date
                        ).year) + "},\n"
            bibtex += "  address = {Geneva},\n"
            bibtex += "  publisher = {Zenodo},\n"
            bibtex += "  doi = {" + dataset["Zenodo"] + "}\n"
            bibtex += "}\n\n"
            sources += [bibtex]
            base_info += [[
                dataset["ID"],
                dataset["ID"],
                meta["title"],
                " AND ".join([c["name"] for c in meta["creators"]]),
                " AND ".join(
                    [c["name"] for c in meta["contributors"] if c["type"] == "Editor"]),
                meta["description"].split("\n")[3][3:-4] if "description" in meta else "",
                dataset["ID"],
                dataset["Zenodo"],
                dataset["Version"]]]
            datasets += [dataset]
                
        with codecs.open(self.raw_dir / "sources.bib", "w", "utf-8") as f:
            for source in sources:
                f.write(source)
            args.log.info("Wrote sources to file.")

        with UnicodeWriter(self.etc_dir / "contributions.csv") as writer:
            writer.writerow(["ID", "Name", "Description", "Creator", "Contributor",
                             "Citation", "Source", "DOI", "Version"])
            for row in base_info:
                writer.writerow(row)
        if UPDATE_DATASETS:
            with UnicodeWriter(
                    self.etc_dir / "datasets-updated.tsv", 
                    delimiter="\t") as writer:
                writer.writerow(list(datasets[0].keys()))
                for row in datasets:
                    writer.writerow(list(row.values()))



    def cmd_makecldf(self, args):
        # concepticon_gloss to concepticon_id conversion
        gloss2id = {
            concept.gloss: concept.id for concept in
            self.concepticon.conceptsets.values()}
        args.log.info("created concepticon gloss to ID converter")
        gcodes = self.glottolog.languoids_by_code()
        
        # read target concepts
        targets, sources = {}, {}
        for row in self.etc_dir.read_csv(
                "concept-modifications.tsv",
                delimiter="\t", dicts=True):
            targets[row["Source"]] = row["Targets"].split(" // ")
            for t in row["Targets"].split(" // "):
                sources[t] = row["Source"]
        args.log.info("loaded concept modifications")

        # only invoke when intending to rerun the full data conversion process
        if RERUN:
            with self.cldf_writer(args) as writer:
                # add sources
                writer.add_sources()
                args.log.info("added sources")
                # add contributions table
                writer.cldf.add_component("ContributionTable")
                writer.cldf.add_columns(
                    "ContributionTable",
                    {"name": "Source", "datatype": "string"},
                    {"name": "DOI", "datatype": "string"},
                    {"name": "Creator", "datatype": "string"},
                    {"name": "Version", "datatype": "string"}
                )
                datasets, contributions = [], {}
                for ds in self.etc_dir.read_csv(
                        "datasets.tsv", 
                        delimiter="\t",
                        dicts=True)[:DATASETS]:
                    datasets += [pycldf.Dataset.from_metadata(
                        self.raw_dir / ds["ID"] / "cldf/cldf-metadata.json"
                    )]
                for row in self.etc_dir.read_csv("contributions.csv", dicts=True)[:DATASETS]:
                    contributions[row["ID"]] = row

                wl: Wordlist = Wordlist(datasets, ts=args.clts.api.bipa)
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
                            if concept and concept.concepticon_gloss:
                                f.write("\t".join([
                                    concept.concepticon_id,
                                    concept.concepticon_gloss,
                                    str(len(set([form.language.glottocode for form in
                                                 concept.forms_with_sounds])))]) + "\n")
                    args.log.info("wrote concept frequencies to file")
                # check for duplicates in the selected concepts
                selected_concepts, visited = [], set()
                for concept in all_concepts:
                    if concept.concepticon_gloss in visited:
                        continue
                    if concept.concepticon_gloss in targets:
                        selected_concepts.extend(targets[concept.concepticon_gloss])
                        for t in targets[concept.concepticon_gloss]:
                            visited.add(t)
                    else:
                        if concept.concepticon_gloss not in gloss2id:
                            dsets = " ".join(set([f.dataset for f in concept.forms]))
                            args.log.info("Concepticon 3-Problem {0} / {1}".format(concept.concepticon_gloss, dsets))
                        else:
                            selected_concepts.append(concept.concepticon_gloss)
                            visited.add(concept.concepticon_gloss)
                selected_concepts = selected_concepts[:CONCEPT_THRESHOLD]
                args.log.info("found {0} valid concepts".format(len(selected_concepts)))
                # calculate the count of concepts per language to filter languages with less than LANGUAGES concepts
                concept_count = {}
                for concept in all_concepts:
                    if concept.concepticon_gloss in selected_concepts:
                        concept_count[concept.concepticon_gloss] = 1
                    elif concept.concepticon_gloss in targets:
                        concept_count[concept.concepticon_gloss] = 0
                        for t in targets[concept.concepticon_gloss]:
                            if t in selected_concepts:
                                concept_count[concept.concepticon_gloss] += 1
                args.log.info(
                    "calculated frequencies for split concepts ({0}/{1})".format(
                        sum([1 for cnc in concept_count.values() if cnc >= 1]),
                        sum(concept_count.values()))
                )
                # get valid languages by counting if they have CONCEPTS_PER_LANGUAGE_THRESHOLD concepts
                valid_language_ids, valid_language_objects = [], []
                for language in sorted(
                        wl.languages,
                        key=lambda forms: sum([
                            concept_count[c.concepticon_gloss] for c in forms.concepts if
                            c.concepticon_gloss in concept_count]),
                        reverse=True
                ):
                    # one can check for common glottocodes here, but we also filter these cases
                    # so the current procedure is to take all languages if they have more than CONCEPTS_PER_LANGUAGE_THRESHOLD
                    # concepts, even if they have the same glottocode but come from different sources
                    cov = sum([concept_count[c.id] for c in language.concepts if
                               c.id in concept_count])
                    if language.latitude and language.glottocode and \
                            cov >= CONCEPTS_PER_LANGUAGE_THRESHOLD and \
                            language.glottocode in gcodes:
                        valid_language_ids.append(language.id)
                        valid_language_objects.append(language)
                args.log.info("found {0} valid languages".format(len(valid_language_ids)))

                # add concepts to the writer now
                for concept in selected_concepts:
                    writer.add_concept(
                        ID=slug(concept, lowercase=True),
                        Name=concept,
                        Concepticon_ID=gloss2id[concept],
                        Concepticon_Gloss=concept,
                        Original_Concept=sources.get(concept, "")
                    )
                clics, accepted_languages, active_contributions = [], [], set()
                for i, language in progressbar(enumerate(valid_language_objects), desc="retrieve forms"):
                    cnc_count, frm_count, lid = 0, 0, str(i+1)
                    for form in language.forms_with_sounds:
                        if form.concept and form.concept.id in selected_concepts:
                            clics += [[
                                lid,
                                form.id,
                                language.dataset,
                                form.concept.id,
                                form.value,
                                form.form,
                                form.sounds,
                                ""
                            ]]
                            cnc_count += 1
                            frm_count += 1
                        elif form.concept and form.concept.id in targets:
                            for gloss in targets[form.concept.id]:
                                if gloss in selected_concepts:
                                    clics += [[
                                        lid,
                                        form.id,
                                        language.dataset,
                                        gloss,
                                        form.value,
                                        form.form,
                                        form.sounds,
                                        form.concept.id]]
                                    cnc_count += 1
                                    frm_count += 1
                    # identifier for family in order to avoid whitespace or
                    # other inconsistencies, for isolates identical with
                    # glottocode
                    if gcodes[language.glottocode].family:
                        family_id = gcodes[language.glottocode].family.id
                    else:
                        family_id = language.glottocode
                    writer.add_language(
                        ID=lid,
                        Name=language.name,
                        Family=family_id, # use slugged form
                        Family_Name=language.family,
                        Latitude=language.latitude,
                        Longitude=language.longitude,
                        Glottocode=language.glottocode,
                        Concept_Count=cnc_count,
                        Form_Count=frm_count,
                        Contribution_ID=language.dataset
                    )
                    accepted_languages += [language.id]
                    active_contributions.add(language.dataset)
                ctrerrors = set()
                # write contributions to CLDF
                for ctr in active_contributions:
                    if not ctr in contributions:
                        ctrerrors.add(ctr)
                    else:
                        writer.objects["ContributionTable"].append(contributions[ctr])
                for ctr in ctrerrors:
                    args.log.info("missing contribution {0} found".format(ctr))
                missing = set()
                for (
                        language_id,
                        form_id,
                        ds_id,
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
                            Source=ds["ID"]
                        )
                    else:
                        missing.add((concept_id, language_id))
                language_table = writer.cldf["LanguageTable"]
                contribution_table = writer.cldf["ContributionTable"]
                for m, lng in missing:
                    args.log.info("Missing concept {0} / {1}".format(m, lng))

        with self.cldf_writer(args, cldf_spec="structure", clean=False) as writer:
            ds = pycldf.Dataset.from_metadata(self.cldf_dir.joinpath("Wordlist-metadata.json"))
            wl = Wordlist(
                [ds],
                ts=args.clts.api.bipa
            )

            graph = get_colexifications(wl)
            for w in ["form", "variety", "language", "family"]:
                normalize_weights(graph, w + "_weight", w + "_count", w + "_count")
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

            # compute neighbors
            neighbors = {}
            for node, data in graph.nodes(data=True):
                neighbors[node] = []
                for node_b in graph[node]:
                    if graph[node][node_b]["family_count"] >= SUBGRAPH_THRESHOLD:
                        neighbors[node].append(node_b)

            pyclics.util.write_gml(graph, self.cldf_dir.joinpath("clics4-graph.gml"))
            with zipfile.ZipFile(
                    self.cldf_dir.joinpath("clics4-graph.gml.zip"),
                    "w",
                    compression=zipfile.ZIP_DEFLATED,
                    compresslevel=9) as zf:
                zf.write(self.cldf_dir.joinpath("clics4-graph.gml"), arcname='clics4-graph.gml')
            self.cldf_dir.joinpath("clics4-graph.gml").unlink()
            args.log.info("computed colexifications")
            # retrieve concepts
            concepts = {row.data["Concepticon_Gloss"]: row for row in ds.objects("ParameterTable")}
            # load language table
            if not RERUN:
                writer.cldf.add_component("LanguageTable")
                writer.cldf.add_columns(
                    "LanguageTable",
                    {"name": "Concept_Count", "datatype": "integer"},
                    {"name": "Form_Count", "datatype": "integer"},
                    {
                        "name": "Contribution_ID",
                        "datatype": "string",
                        "propertyUrl": "http://cldf.clld.org/v1.0/terms.rdf#contributionReference"
                        }
                )

            else:
                writer.cldf.add_component(language_table)
                writer.cldf.add_component(contribution_table)
            writer.cldf.add_columns(
                "ParameterTable",
                {"name": "Source_Concept", "datatype": "string"},
                {"name": "Target_Concept", "datatype": "string"},
                {"name": "Form_Count", "datatype": "integer"},
                {"name": "Variety_Count", "datatype": "integer"},
                {"name": "Language_Count", "datatype": "integer"},
                {"name": "Family_Count", "datatype": "integer"},
                {"name": "Variety_Weight", "datatype": "float"},
                {"name": "Language_Weight", "datatype": "float"},
                {"name": "Family_Weight", "datatype": "float"},
                {"name": "Forms", "datatype": {"base": "string"}, "separator": " "},
                {"name": "Varieties", "datatype": {"base": "string"}, "separator": " "},
                {"name": "Languages", "datatype": {"base": "string"}, "separator": " "},
                {"name": "Families", "datatype": {"base": "string"}, "separator": " "}
            )
            col = writer.cldf.add_table("concepts.csv")
            writer.cldf.add_columns(
                "concepts.csv",
                {
                    "name": "ID",
                    "datatype": "string",
                    "propertyUrl": "http://cldf.clld.org/v1.0/terms.rdf#id"
                },
                {
                    "name": "Concepticon_ID",
                    "datatype": "string",
                    "propertyUrl": "http://cldf.clld.org/v1.0/terms.rdf#concepticonReference"
                 },
                {
                    "name": "Concepticon_Gloss",
                    "datatype": "string",
                },
                {
                    "name": "Original_Concept",
                    "datatype": "string"
                },
                {"name": "Form_Count", "datatype": "integer"},
                {"name": "Variety_Count", "datatype": "integer"},
                {"name": "Language_Count", "datatype": "integer"},
                {"name": "Family_Count", "datatype": "integer"},
                {"name": "Community", "datatype": "string", "null": "?"},
                {"name": "CentralConcept", "datatype": "string", "null": "?"},
                {"name": "Forms", "datatype": {"base": "string"}, "separator": " "},
                {"name": "Varieties", "datatype": {"base": "string"}, "separator": " "},
                {"name": "Languages", "datatype": {"base": "string"}, "separator": " "},
                {"name": "Families", "datatype": {"base": "string"}, "separator": " "},
                {"name": "Neighbors", "datatype": "string", "separator": " // "},
                {"name": "Similarities", "datatype": "json"}
            )
            col.tableSchema.primaryKey = ["Concepticon_ID"]
            # compute missing data for all nodes
            for idf, (nodeA, nodeB, data) in progressbar(
                    enumerate(graph.edges(data=True)),
                    desc="writing colexifications"):
                idx = str(idf+1)
                # compute missing data
                negative_data = []
                for language in wl.languages:
                    if language.id not in data["languages"]:
                        if nodeA in language.concepts and nodeB in language.concepts:
                            negative_data.append(language.id)

                writer.objects["ParameterTable"].append(
                    {
                        "ID": idx,
                        "Name": "{0}/{1}".format(nodeA, nodeB),
                        "Description": "Colexification of {0} and {1}.".format(nodeA, nodeB),
                        "Source_Concept": nodeA,
                        "Target_Concept": nodeB,
                        "Form_Count": data["form_count"],
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
                    }
                )
                if data["family_count"] >= COLEXIFICATION_THRESHOLD:
                    for language_id in data["varieties"]:
                        writer.objects["ValueTable"].append(
                            {
                                "ID": idx + "-" + language_id,
                                "Parameter_ID": idx,
                                "Language_ID": language_id,
                                "Value": 1
                            }
                        )
                    # now add missing data
                    for language_id in negative_data:
                        writer.objects["ValueTable"].append(
                            {
                                "ID": idx + "-" + language_id,
                                "ParameterID": idx,
                                "Language_ID": language_id,
                                "Value": 0
                            }
                        )

            # extend graph by adding missing edges
            args.log.info("computing similarities")
            for nodeA, nodeB in itertools.combinations(list(graph.nodes), r=2):
                if nodeB in graph[nodeA]:
                    continue
                graph.add_edge(nodeA, nodeB, family_weight=1 / 100000)
            transition_matrix, node_list, _ = get_transition_matrix(
                graph, steps=10, weight="family_weight", normalize=True
            )
            args.log.info("computed similarity matrix")
            # compute pairwise concept similarities based on random walks
            similarities = {}
            for i, nodeA in enumerate(node_list):
                similarities[nodeA] = {}
                for j, nodeB in enumerate(node_list):
                    if transition_matrix[i][j] >= MINIMAL_SIMILARITY:
                        similarities[nodeA][nodeB] = transition_matrix[i][j]
            for concept in map(lambda x: x.id, wl.concepts):
                if concept not in community_labels:
                    args.log.info("Concept {0} without community.".format(concept))
                if concept not in neighbors:
                    neighbors[concept] = []
                writer.objects["concepts.csv"].append(
                    {
                        "ID": concepts[concept].id,
                        "Concepticon_ID": gloss2id[concept],
                        "Concepticon_Gloss": concept,
                        "Original_Concept": concepts[concept].data["Original_Concept"],
                        "Form_Count": graph.nodes[concept]["form_count"],
                        "Variety_Count": graph.nodes[concept]["variety_count"],
                        "Language_Count": graph.nodes[concept]["language_count"],
                        "Family_Count": graph.nodes[concept]["family_count"],
                        "Community": community_labels[concept][0],
                        "CentralConcept": community_labels[concept][1],
                        "Similarities": similarities.get(concept, {}),
                        "Forms": graph.nodes[concept]["forms"],
                        "Varieties": graph.nodes[concept]["varieties"],
                        "Languages": list(set(graph.nodes[concept]["languages"])),
                        "Families": list(set(graph.nodes[concept]["families"])),
                        "Neighbors": neighbors[concept]
                    }
                )
