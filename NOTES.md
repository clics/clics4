# CLICS 4: Workflow for Data Generation

The CLICS 4 workflow differs slightly from the workflow we have used in [CLICS3](https://github.com/clics/clics3). We now have drastically increased the number of datasets, but we have also made sure to use stricter selection criteria for the languages to be included. This also results in different numbers with respect to the number of concepts and the number of language varieties. 

## How to Cite CLICS 4?

If you use the data in your work, make sure to cite the correct version that you are using. For the currently most recent version, we recommend to cite it as follows:

> Tjuka, Annika; Forkel, Robert; Rzymski, Christoph; and List, Johann-Mattis (2025): CLICS 4: An Improved Database of Cross-Linguistic Colexifications [Dataset Version 0.5]. Passau: MCL Chair at the University of Passau. https://github.com/clics/clics4/

Since the whole workflow underlying CLICS 4 regardless of the individual versions will be presented in a freely available publication, we also appreciate if you cite this forthcoming paper (already available as preprint):

> Tjuka, Annika; Forkel, Robert; Rzymski, Christoph; and List, Johann-Mattis (forthcoming): Advancing the Database of Cross-Linguistic Colexifications with New Workflows and Data. Proceedings of the 16th International Conference on Computational Semantics (IWCS). Düsseldorf: Association for Computational Linguistics. 1-15. Preprint: https://doi.org/10.48550/arXiv.2503.11377

## What is New in Comparison with CLICS³?

The following points summarize major differences between CLICS³ and CLICS⁴:

- more datasets in CLICS 4: CLICS 4 now uses 98 datasets, while CLICS³ used 30
- fully transcribed data instead of data in orthography: CLICS 4 now uses data fully transcribed to IPA, ignoring all datasets that only offer orthography (this results in fewer languages at times, despite the increase in datasets)
- treatment of concepts: we now model some "hidden" colexifications that have been ignored before, since the concept identifiers in Concepticon cover two separate concepts that are frequently colexified as one single concept, as separate concepts (these are marked in the CLDF representation)
- we provide a full-fledged CLDF dataset now, in which the concept network is also modeled with the help of CLDF

## Workflow for Data Aggregation

In the following, we run those interested in trying the workflow that we applied to construct CLICS 4 on their own machines through the workflow in due detail. To run the workflow, we assume that users have enough experience with Python in order to know how to create their own fresh virtual environment and know how to run commands in the terminal. 

### W1: Install Packages

All you need to install the packages required is to install the current package with [PIP](https://pypi.org/project/pip) as follows (using a fresh virtual environment), after having downloaded the `clics4` package with [GIT](https://git-scm.com). The following lines also obtain the version that we used in this demo.
```
$ git clone https://github.com/clics/clics4.git
$ cd clics4
$ git checkout v0.5
$ pip install -e .
```

## W2: Download Data

In order to do a fresh download of all the data that we use in CLICS 4, you need to run the following command:

```
$ cldfbench download lexibank_clics4.py
```

## W3: Create CLICS 4 Dataset

Before you can run the code, you must make sure to have downloaded all data and also obtained actual copies of Glottolog, Concepticon, and CLTS. An easy way to obtain these with the help of `cldfbench` is to run the command `cldfbench catconfig` and follow instructions there. If you use a Windows machine, you will need some additional preparations (see [Snee 2024](https://calc.hypotheses.org/7852)), so we kindly ask you to follow the respective instructions in Snee (2024).

If you have successfully run the `catconfig` subcommand, just type:

```
$ cldfbench lexibank.makecldf --glottolog-version=v5.2.1 --concepticon-version=v3.4.0 --clts-version=v2.3.0 lexibank_clics4.py
```

In the other case, specify the explicit locations of the repositories for Glottolog, Concepticon, and CLTS as follwo.

```
cldfbench lexibank.makecldf --glottolog-repos=Path2Glottolog --concepticon-repos=Path2Concepticon --clts-repos=Path2Clics --glottolog-version=v5.2.1 --concepticon-version=v3.4.0 --clts-version=v2.3.0 lexibank_clics4.py
```

## W4: CLLD Version of CLICS 4

This release is a CLICS 4 dataset that we consider generally good enough with respect to the data to be used in publications (small errors would always be possible with such large numbers of data aggregated from different sources). However, we emphasize that there are a couple of shortcomings for now that we will try to handle before publishing a new web-based version of CLICS that succeeds the current version 3.0 at https://clics.clld.org. Before publishing this new CLLD version of CLICS 4, we will implement a new representation of the data in order to adhere to the representation of ParameterNetworks in the new [CLDF specification](https://cldf.clld.org).  
