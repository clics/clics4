"""Lexibank Script for CLICS⁴"""
import json
import time
import codecs
import pathlib
import warnings
import functools
import collections
from collections.abc import Generator
import contextlib
import dataclasses
import itertools
import zipfile
from typing import Any

import networkx as nx
import pylexibank.dataset
from cldfbench import CLDFSpec as CldfBenchSpec
from pylexibank.cldf import LexibankWriter
from pylexibank import Dataset as BaseDataset
from cltoolkit import Wordlist
from clldutils.misc import slug
from lingpy.convert.graph import networkx2igraph
from csvw.dsv import UnicodeWriter, reader
from cldfzenodo import API as cldfzenodoapi
import pycldf
import nameparser
import attr

from pyclics.colexifications import (
    get_colexifications, get_transition_matrix, normalize_weights, Graph)
import pyclics.util

from pylexibank import Concept, Lexeme, Language, progressbar

CONCEPTS_PER_LANGUAGE_THRESHOLD = 180
CONCEPT_THRESHOLD = 1800
WRITE_CONCEPTS = True
RERUN = True
SUBGRAPH_THRESHOLD = 3
DATAFILE = "lexibank.tsv"
MINIMAL_SIMILARITY = 0.01
COLEXIFICATION_THRESHOLD = 2
UPDATE_DATASETS = False
WITH_TOKEN = False
SEP = " // "

CommunityIndexType = str
NodeNameType = str
# Map nodes to pairs (community, central concept):
CommunityMapType = dict[NodeNameType, tuple[CommunityIndexType, NodeNameType]]


@contextlib.contextmanager
def timed(log, desc):
    log.info(desc + '...')
    s = time.time()
    yield
    log.info('...done [%.1f]', time.time() - s)


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
    Families = attr.ib(default=None, metadata={"format": "string", "separator":  SEP})
    Neighbors = attr.ib(default=None, metadata={"format": "string", "separator": SEP})
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
        sources = pycldf.Sources.from_file(self.raw_dir / "base-sources.bib")
        contributions = []
        for row in self.etc_dir.read_csv(
                DATAFILE, delimiter="\t",
                dicts=True):
            dataset = row["ID"]

            if row["ClicsCore"].strip() != "x":
                print('skipping {0}'.format(dataset))
                continue
            # get updated version via zenodo
            args.log.info("Processing dataset {0}".format(dataset))
            dest = self.raw_dir / dataset
            record = cldfzenodoapi.get_record(row["Zenodo"])
            time.sleep(2)
            if dest.exists():
                pass
                #args.log.info("Removing old download in {0}".format(dataset))
                #shutil.rmtree(dest)
            else:
                args.log.info("Downloading dataset {0}".format(dataset))
                rec_new = record.from_concept_doi(record.concept_doi)
                time.sleep(2)
                if rec_new.doi != record.doi:
                    record = rec_new
                    args.log.warn("DOI for datasets {0} is not the latest version!".format(
                        dataset))
                record.download(dest)
                time.sleep(2)

            # load zenodo info to make a new bibtex and doi
            with open(self.raw_dir / dataset / ".zenodo.json", encoding='utf8') as f:
                meta = json.load(f)
            editors = [c["name"] for c in meta["contributors"] if
                       c["type"] == "Editor"]
            for i, editor in enumerate(editors):
                name = nameparser.HumanName(editor)
                first = name.first
                if name.middle:
                    first = " " + name.middle
                editors[i] = f"{name.last}, {first}"
            
            # load normal metadata to get the original citation
            with open(self.raw_dir / dataset / "metadata.json", encoding='utf8') as f:
                meta = json.load(f)
            description = meta["citation"]
            # create bibtex and write to new file
            bib = dict(author=" and ".join(record.creators),
                    title=record.title,
                    publisher="Zenodo",
                    year=record.year,
                    address="Geneva",
                    doi=record.doi)
            if editors:
                bib["editor"] = " and ".join(editors)
            if description:
                bib["citation"] = description

            sources.add(pycldf.Source(
                    "book",
                    row["ID"],
                    **bib))
            # check if source is in sources
            for src_key in row["Source"].split(" "):
                if src_key not in sources:
                    args.log.warn("source with key '{0}' missing in data".format(src_key))
            contributions += [[
                row["ID"],
                row["Dataset"],
                bib["title"],
                bib["author"],
                bib.get("editor", ""),
                bib.get("citation", ""),
                row["Source"],
                bib["doi"],
                row["Version"]]]
        with codecs.open(self.raw_dir / "sources.bib", "w", "utf-8") as f:
            for source in sources:
                f.write(source.bibtex() + "\n\n")

        # write contributions to file
        with UnicodeWriter(self.etc_dir / "contributions.csv") as writer:
            writer.writerow(["ID", "Name", "Description", "Creator",
                             "Contributor", "Citation", "Source", "DOI",
                             "Version"])
            for row in contributions:
                writer.writerow(row)

    def cmd_makecldf(self, args):
        with timed(args.log, 'Loading Concepticon data'):
            gloss2id = {concept.gloss: concept.id for concept in self.concepticon.conceptsets.values()}

        # We create two CLDF datasets sharing language and contribution table.
        language_table, contribution_table = None, None
        if RERUN:
            with timed(args.log, 'Creating CLDF Wordlist'):
                language_table, contribution_table = self._makecldf_wordlist(args, gloss2id)

        with timed(args.log, 'Creating CLDF StructureDataset'):
            self._makecldf_structure_dataset(args, gloss2id, language_table, contribution_table)

    def _makecldf_structure_dataset(self, args, gloss2id, language_table, contribution_table):
        """
        The StructureDataset provides the actual colexification data. Its parameters are pairs of
        colexified Concepticon concepts.
        """
        with self.cldf_writer(args, cldf_spec="structure", clean=False) as writer:
            self._add_structure_dataset_schema(writer, language_table, contribution_table)

            with timed(args.log, 'Loading wordlist'):  # 466.0 secs
                wl = self._get_cltoolkit_wordlist(args.clts.api.bipa, [self.cldf_reader()])

            # Create the colexification graph:
            with timed(args.log, "Computing colexification graph"):  # 52.4 secs
                g = ClicsGraph.from_wordlist(wl)
                g.write(self.cldf_dir.joinpath("clics4-graph.gml"))

            concepts = {row.data["Concepticon_Gloss"]: row for row in self.cldf_reader().objects("ParameterTable")}

            wl_languages = sorted(wl.languages, key=lambda lg: lg.id)
            wl_languages = [(lg, {c.concepticon_gloss for c in lg.concepts}) for lg in wl_languages]

            # Compute missing data for all nodes:
            with timed(args.log, 'Writing colexifications'):  # 82.4 secs
                for clx in progressbar(g.iter_colexifications(), desc="writing colexifications", leave=True):
                    writer.objects["ParameterTable"].append(clx.asdict())

                    for lid in sorted(set(clx.Varieties)):
                        writer.objects["ValueTable"].append(clx.make_value(1, lid))
                    # now add missing data
                    seen = set()
                    for language, cset in wl_languages:
                        if language.id in seen:
                            continue
                        seen.add(language.id)
                        if language.id in clx.Languages:
                            continue
                        if {clx.Source_Concept, clx.Target_Concept}.issubset(cset):
                            # Language which has both source and target concept but does not
                            # colexify them.
                            lid = language.id.split("-")[1]
                            writer.objects["ValueTable"].append(clx.make_value(0, lid))

            # extend graph by adding missing edges
            with timed(args.log, "Computing similarities"):  # 23.3 secs
                g.compute_similarities()

            # retrieve Concepticon concepts - the Parameters of the Wordlist:
            for concept in map(lambda x: x.id, wl.concepts):
                if concept not in g.community_labels:
                    args.log.info("Concept %s without community.", concept)
                if concept not in g.neighbors:
                    g.neighbors[concept] = []
                kw = {
                    "ID": concepts[concept].id,
                    "Concepticon_ID": gloss2id[concept],
                    "Concepticon_Gloss": concept,
                    "Original_Concept": concepts[concept].data["Original_Concept"]
                }
                kw.update(g.get_concept_data(concept))
                writer.objects["concepts.csv"].append(kw)

    def _add_structure_dataset_schema(self, writer, language_table, contribution_table):
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
        writer.cldf.add_columns("ParameterTable", *Colexification.colspecs())
        tbl = writer.cldf.add_table(
            "concepts.csv",
            {
                "name": "ID",
                "datatype": "string",
                "propertyUrl": "http://cldf.clld.org/v1.0/terms.rdf#id"
            },
            {"name": "Name", "datatype": "string"},
            {
                "name": "Concepticon_ID",
                "datatype": "string",
                "propertyUrl": "http://cldf.clld.org/v1.0/terms.rdf#concepticonReference"
            },
            {"name": "Concepticon_Gloss", "datatype": "string"},
            {"name": "Original_Concept", "datatype": "string"},
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
            {"name": "Neighbors", "datatype": "string", "separator": SEP},
            {"name": "Similarities", "datatype": "json"}
        )
        tbl.tableSchema.primaryKey = ["Concepticon_ID"]

    def _makecldf_wordlist(self, args, gloss2id):
        gcodes = self.glottolog.languoids_by_code()

        # read target concepts
        cm = ConceptModifications.from_file(self.etc_dir / "concept-modifications.tsv")
        args.log.info("loaded concept modifications")

        with self.cldf_writer(args) as writer:
            writer.add_sources()
            args.log.info("added sources")

            writer.cldf.add_component(
                "ContributionTable",
                {"name": "Source", "datatype": "string"},
                {"name": "DOI", "datatype": "string"},
                {"name": "Creator", "datatype": "string"},
                {"name": "Version", "datatype": "string"}
            )

            with timed(args.log, 'Loading wordlist'):
                wl = ClicsWordlist.from_cltoolkit_wordlist(
                    self._get_cltoolkit_wordlist(args.clts.api.bipa), cm, gloss2id)

            if WRITE_CONCEPTS:
                wl.write_concept_frequencies(self.etc_dir.joinpath("concepts.tsv"))
                args.log.info("wrote concept frequencies to file")
            # check for duplicates in the selected concepts
            args.log.info("found %s valid concepts", len(wl.selected_concepts))
            # calculate the count of concepts per language to filter languages with less than LANGUAGES concepts
            args.log.info(
                "calculated frequencies for split concepts (%s/%s)",
                sum(1 for cnc in wl.concept_count.values() if cnc >= 1),
                sum(wl.concept_count.values()))

            # get valid languages by counting if they have CONCEPTS_PER_LANGUAGE_THRESHOLD concepts
            valid_languages = wl.valid_languages(gcodes)
            args.log.info("found %s valid languages", len(valid_languages))

            # add concepts to the writer now
            for concept in wl.selected_concepts:
                writer.add_concept(
                    ID=slug(concept, lowercase=True),
                    Name=concept,
                    Concepticon_ID=gloss2id[concept],
                    Concepticon_Gloss=concept,
                    Original_Concept=cm.target_to_source.get(concept, "")
                )

            active_contributions = set()
            forms = FormAggregator()
            with timed(args.log, 'Aggregating forms'):
                for i, language in progressbar(enumerate(valid_languages.values()), desc="forms"):
                    lid = str(i + 1)
                    cnc_count, frm_count = forms.add_language(
                        lid, language, wl.selected_concepts, cm.source_to_targets)
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
                        Family=family_id,  # use slugged form
                        Family_Name=language.family,
                        Latitude=language.latitude,
                        Longitude=language.longitude,
                        Glottocode=language.glottocode,
                        Concept_Count=cnc_count,
                        Form_Count=frm_count,
                        Contribution_ID=language.dataset
                    )
                    active_contributions.add(language.dataset)
            args.log.info("excluded %s duplicates", len(forms.excluded))
            forms.write_excluded(self.raw_dir / "duplicates.md")

            contributions = {
                row['ID']: row for row in self.etc_dir.read_csv("contributions.csv", dicts=True)}
            ctrerrors = set()
            # write contributions to CLDF
            for ctr in active_contributions:
                if ctr in contributions:
                    writer.objects["ContributionTable"].append(contributions[ctr])
                    continue
                ctrerrors.add(ctr)
            for ctr in ctrerrors:
                args.log.info("missing contribution %s found", ctr)
            missing = set()
            for f in progressbar(forms.forms, desc="adding forms"):
                if f.concept_id in wl.selected_concepts:
                    writer.add_form_with_segments(
                        Local_ID=f.form_id,
                        Parameter_ID=slug(f.concept_id, lowercase=True),
                        Language_ID=f.language_id,
                        Value=f.form_val,
                        Form=f.form_form,
                        Segments=f.form_sounds,
                        ConceptInSource=f.concept_in_source,
                        Source=f.dataset
                    )
                    continue
                missing.add((f.concept_id, f.language_id))
            for m, lng in missing:
                args.log.info("Missing concept %s / %s", m, lng)
        return writer.cldf["LanguageTable"], writer.cldf["ContributionTable"]

    def _get_cltoolkit_wordlist(self, bipa, datasets=None) -> Wordlist:
        def _iter_datasets():
            if datasets:
                yield from datasets
            else:
                i = 0
                for ds in self.etc_dir.read_csv(DATAFILE, delimiter="\t", dicts=True):
                    if ds["ClicsCore"].strip() == "x":
                        yield pycldf.Dataset.from_metadata(
                            self.raw_dir / ds["ID"] / "cldf/cldf-metadata.json")
                        i += 1
                        #if i > 10:
                        #    break
        return Wordlist(_iter_datasets(), ts=bipa)


@dataclasses.dataclass(frozen=True)
class Colexification:
    ID: str
    Name: str
    Description: str
    Source_Concept: str
    Target_Concept: str
    Form_Count: int
    Variety_Count: int
    Language_Count: int
    Family_Count: int
    Variety_Weight: float
    Language_Weight: float
    Family_Weight: float
    Forms: list[str]  # FIXME: remove the "clics4-" prefix!
    Varieties: list[str]
    Languages: list[str]
    Families: list[str]

    @classmethod
    @functools.lru_cache(maxsize=1)
    def fields(cls):
        return dataclasses.fields(cls)

    @classmethod
    @functools.lru_cache(maxsize=10)
    def field_names(cls, exclude):
        return [(f.name, f.name.lower()) for f in cls.fields() if f.name not in exclude]

    @classmethod
    def from_edge(cls, idx, nodeA, nodeB, data):
        kw = {
            "ID": idx,
            "Name": f"{nodeA}/{nodeB}",
            "Description": f"Colexification of {nodeA} and {nodeB}.",
            "Source_Concept": nodeA,
            "Target_Concept": nodeB,
        }
        #for field, fieldl in cls.field_names(tuple(kw.keys())):
        #    kw[field] = data[fieldl]
        for f in (
                'Form_Count',
                'Variety_Count',
                'Language_Count',
                'Family_Count',
                'Variety_Weight',
                'Language_Weight',
                'Family_Weight',
                'Forms',
                'Varieties',
                'Languages',
                'Families'
        ):
            kw[f] = data[f.lower()]
        return cls(**kw)

    @classmethod
    def colspecs(cls):
        res = []
        for field in cls.fields():
            if field.name in {'ID', 'Name', 'Description'}:
                continue
            spec = {"name": field.name, "datatype": 'string'}
            if cls.__annotations__[field.name] == int:
                spec['datatype'] = 'integer'
            elif cls.__annotations__[field.name] == float:
                spec['datatype'] = 'float'
            elif cls.__annotations__[field.name] == float:
                spec['datatype'] = 'float'
            elif cls.__annotations__[field.name] == list[str]:
                spec['separator'] = ' '
            res.append(spec)
        return res

    def asdict(self):
        return {k.name: getattr(self, k.name) for k in self.fields()}

    def make_value(self, val, lid):
        return {
            "ID": self.ID + "-" + lid,
            "Parameter_ID": self.ID,
            "Language_ID": lid.split("-")[-1],
            "Value": val,
            "Source": ["Tjuka2025"]
        }


@dataclasses.dataclass
class ClicsGraph:
    """A ClicsGraph has Concepticon concepts as nodes and colexifications as edges."""
    graph: Graph
    community_labels: CommunityMapType
    neighbors: dict[NodeNameType, list[NodeNameType]]
    similarities: dict[NodeNameType, dict[NodeNameType, float]] = dataclasses.field(
        default_factory=dict)

    @classmethod
    def from_graphml(cls, p):
        gml = pathlib.Path(p).read_text(encoding='utf8')
        ascii = pathlib.Path('ascii.gml')
        ascii.write_bytes(gml.encode('ascii', 'ignore'))
        return cls(
            nx.read_gml(ascii),
            {},
            {})

    @classmethod
    def from_wordlist(cls, wl):
        graph = get_colexifications(wl)
        for w in ["form", "variety", "language", "family"]:
            normalize_weights(graph, w + "_weight", w + "_count", w + "_count")

        # Add "community" and "central_concept" annotations to nodes.
        ig = networkx2igraph(graph)
        communities = ig.community_infomap(
            edge_weights="family_weight", vertex_weights="family_count")
        community_labels = {}
        for i, nodes_ in enumerate(communities, start=1):
            nodes = [ig.vs[node]["Name"] for node in nodes_]
            central_node = sorted(
                nx.degree(graph, nodes, weight="family_weight"),
                key=lambda x: x[1],
                reverse=True)[0][0]
            for node in nodes:
                community_labels[node] = (str(i), central_node)
                graph.nodes[node]["community"] = str(i)
                graph.nodes[node]["central_concept"] = central_node

        neighbors: dict[NodeNameType, list[NodeNameType]] = {}
        for node, data in graph.nodes(data=True):
            neighbors[node] = []
            for node_b in graph[node]:
                if graph[node][node_b]["family_count"] >= SUBGRAPH_THRESHOLD:
                    neighbors[node].append(node_b)
        return cls(graph, community_labels, neighbors)

    def compute_similarities(self):
        for nodeA, nodeB in itertools.combinations(list(self.graph.nodes), r=2):
            if nodeB in self.graph[nodeA]:
                continue
            self.graph.add_edge(nodeA, nodeB, family_weight=1 / 100000)
        transition_matrix, node_list, _ = get_transition_matrix(
            self.graph, steps=10, weight="family_weight", normalize=True)
        # compute pairwise concept similarities based on random walks
        for i, nodeA in enumerate(node_list):
            self.similarities[nodeA] = {}
            for j, nodeB in enumerate(node_list):
                if transition_matrix[i][j] >= MINIMAL_SIMILARITY:
                    self.similarities[nodeA][nodeB] = transition_matrix[i][j]

    def write(self, p):
        pyclics.util.write_gml(self.graph, p)
        with zipfile.ZipFile(
                p.parent / f'{p.name}.zip',
                "w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=9) as zf:
            zf.write(p, arcname=p.name)
            p.unlink()

    def iter_colexifications(self) -> Generator[Colexification, None, None]:
        for i, (node_a, node_b, data) in enumerate(self.graph.edges(data=True)):
            if data['family_count'] >= COLEXIFICATION_THRESHOLD:
                yield Colexification.from_edge(str(i + 1), node_a, node_b, data)

    def get_concept_data(self, concept: NodeNameType) -> dict[str, Any]:
        return {
            "Form_Count": self.graph.nodes[concept]["form_count"],
            "Variety_Count": self.graph.nodes[concept]["variety_count"],
            "Language_Count": self.graph.nodes[concept]["language_count"],
            "Family_Count": self.graph.nodes[concept]["family_count"],
            "Community": self.community_labels[concept][0],
            "CentralConcept": self.community_labels[concept][1],
            "Similarities": collections.OrderedDict(
                (k, round(v, 4)) for k, v in sorted(self.similarities.get(concept, {}).items())
            ),
            "Forms": [s.removeprefix('clics4-') for s in self.graph.nodes[concept]["forms"]],
            "Varieties": [s.removeprefix('clics4-') for s in self.graph.nodes[concept]["varieties"]],
            "Languages": list(set(self.graph.nodes[concept]["languages"])),
            "Families": list(set(self.graph.nodes[concept]["families"])),
            "Neighbors": self.neighbors[concept]
        }


@dataclasses.dataclass
class Deduplicator:
    selected_concepts: list = dataclasses.field(default_factory=list)
    visited: set = dataclasses.field(default_factory=set)

    @classmethod
    def from_data(cls, all_concepts, targets, gloss2id):
        res = cls()
        for concept in all_concepts:
            if concept.concepticon_gloss in res.visited:
                continue
            if concept.concepticon_gloss in targets:
                res.selected_concepts.extend(targets[concept.concepticon_gloss])
                res.visited |= set(targets[concept.concepticon_gloss])
                continue
            if concept.concepticon_gloss not in gloss2id:
                dsets = " ".join(set([f.dataset for f in concept.forms]))
                warnings.warn("Concepticon 3-Problem %s / %s", concept.concepticon_gloss, dsets)
                continue
            res.selected_concepts.append(concept.concepticon_gloss)
            res.visited.add(concept.concepticon_gloss)
        return res


@dataclasses.dataclass(frozen=True)
class ClicsWordlist:
    wl: Wordlist
    all_concepts: list
    selected_concepts: list
    concept_count: dict[str, int]

    @classmethod
    def from_cltoolkit_wordlist(cls, wl, cm, gloss2id):
        # sort the concepts by number of unique glottocodes
        all_concepts = sorted(
            wl.concepts,
            key=lambda x: len({form.language.glottocode for form in x.forms_with_sounds}),
            reverse=True)

        dedup = Deduplicator.from_data(all_concepts, cm.source_to_targets, gloss2id)
        selected_concepts = dedup.selected_concepts[:CONCEPT_THRESHOLD]

        cc = {}
        for concept in all_concepts:
            if concept.concepticon_gloss in selected_concepts:
                cc[concept.concepticon_gloss] = 1
            elif concept.concepticon_gloss in cm.source_to_targets:
                cc[concept.concepticon_gloss] = 0
                for t in cm.source_to_targets[concept.concepticon_gloss]:
                    if t in selected_concepts:
                        cc[concept.concepticon_gloss] += 1
        return cls(wl, all_concepts, selected_concepts, cc)

    def write_concept_frequencies(self, p):
        with UnicodeWriter(p, delimiter='\t') as w:
            w.writerow(["ID", "GLOSS", "FREQUENCY"])
            for concept in self.all_concepts:
                if concept and concept.concepticon_id and concept.concepticon_gloss:
                    w.writerow([
                        concept.concepticon_id,
                        concept.concepticon_gloss,
                        str(len({form.language.glottocode for form in concept.forms_with_sounds}))])

    def valid_languages(self, gcodes):
        # get valid languages by counting if they have CONCEPTS_PER_LANGUAGE_THRESHOLD concepts
        valid_languages = collections.OrderedDict()
        for language in sorted(
                self.wl.languages,
                key=lambda forms: sum(
                    self.concept_count[c.concepticon_gloss] for c in forms.concepts if
                    c.concepticon_gloss in self.concept_count),
                reverse=True
        ):
            # one can check for common glottocodes here, but we also filter these cases
            # so the current procedure is to take all languages if they have more than CONCEPTS_PER_LANGUAGE_THRESHOLD
            # concepts, even if they have the same glottocode but come from different sources
            cov = sum([self.concept_count[c.id] for c in language.concepts if
                       c.id in self.concept_count])
            if language.latitude and language.glottocode and \
                    cov >= CONCEPTS_PER_LANGUAGE_THRESHOLD and \
                    language.glottocode in gcodes:
                valid_languages[language.id] = language
        return valid_languages


@dataclasses.dataclass
class ConceptModifications:
    source_to_targets: dict[str, list[str]]
    target_to_source: dict[str, str]

    @classmethod
    def from_file(cls, p):
        # read target concepts
        targets, sources = {}, {}
        for row in reader(p, delimiter="\t", dicts=True):
            targets[row["Source"]] = row["Targets"].split(SEP)
            for t in row["Targets"].split(SEP):
                sources[t] = row["Source"]
        return cls(targets, sources)


@dataclasses.dataclass
class Form:
    language_id: str
    form_id: str
    ds_id: str
    concept_id: str
    form_val: str
    form_form: str
    form_sounds: str
    concept_in_source: str
    dataset: str


@dataclasses.dataclass
class FormAggregator:
    forms: list[Form] = dataclasses.field(default_factory=list)
    excluded: list = dataclasses.field(default_factory=list)

    def add_language(self, lid, language, selected_concepts, targets):
        cnc_count, frm_count = 0, 0
        duplicates = set()
        for form in language.forms_with_sounds:
            check_form = "{0}-{1}".format(
                form.concept.id if form.concept else "", str(form.sounds))
            if form.concept and form.concept.id in selected_concepts and check_form not in duplicates:
                duplicates.add(check_form)
                self.forms.append(Form(
                    lid,
                    form.id,
                    language.dataset,
                    form.concept.id,
                    form.value,
                    form.form,
                    form.sounds,
                    "",
                    form.dataset
                ))
                cnc_count += 1
                frm_count += 1
            elif form.concept and form.concept.id in targets and check_form not in duplicates:
                duplicates.add(check_form)
                for gloss in targets[form.concept.id]:
                    if gloss in selected_concepts:
                        self.forms.append(Form(
                            lid,
                            form.id,
                            language.dataset,
                            gloss,
                            form.value,
                            form.form,
                            form.sounds,
                            form.concept.id,
                            form.dataset))
                        cnc_count += 1
                        frm_count += 1
            elif check_form in duplicates:
                self.excluded.append(form)
        return cnc_count, frm_count

    def write_excluded(self, p):
        with open(p, "w") as f:
            f.write("# Duplicates\n\n")
            f.write("ID | Language | Concept | Form | Sounds \n")
            f.write("--- | --- | --- | --- | ---\n")
            for form in self.excluded:
                f.write(" | ".join([
                    form.id,
                    form.language.name,
                    form.concept.concepticon_gloss,
                    form.form, str(form.sounds)]) + "\n")
