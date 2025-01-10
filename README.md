# CLICS⁴

## How to cite

If you use these data please cite
- the original source
  > Tjuka, Annika; Forkel, Robert; Rzymski, Christoph; and List, Johann-Mattis (2025): CLICS⁴: An Improved Database of Cross-Linguistic Colexifications [Dataset, Version 0.4]. Passau: MCL Chair at the University of Passau.
- the derived dataset using the DOI of the [particular released version](../../releases/) you were using

## Description


This dataset is licensed under a CC-BY-4.0 license

Available online at https://clics.clld.org

## Notes

# CLICS4: Workflow

The CLICS4 workflow differs slightly from the workflow we have used in [CLICS3](https://github.com/clics/clics3). We now have drastically increased the number of datasets, but we have also made sure to use stricter selection criteria for the languages to be included. This also results in different numbers with respect to the number of concepts and the number of language varieties. 

## How to Cite CLICS⁴?

> Tjuka, Annika; Forkel, Robert; Rzymski, Christoph; and List, Johann-Mattis (2025): CLICS⁴: An Improved Database of Cross-Linguistic Colexifications [Dataset Version 0.4]. Passau: MCL Chair at the University of Passau.

## W1: What is New in Comparison with CLICS³?

The following points summarize major differences between CLICS³ and CLICS⁴:

- more datasets in CLICS⁴: CLICS⁴ now uses 98 datasets, while CLICS³ used 30
- fully transcribed data instead of data in orthography: CLICS⁴ now uses data fully transcribed to IPA, ignoring all datasets that only offer orthography (this results in fewer languages at times, despite the increase in datasets)
- 


## W.1: Install Packages

All you need to install the packages required is to install the current package with [PIP](https://pypi.org/project/pip) as follows (using a fresh virtual environment), after having downloaded the `clics4` package with [GIT](https://git-scm.com). The following lines also obtain the version that we used in this demo.
```
$ git clone https://github.com/clics/clics4.git
$ cd clics4
$ git checkout v0.4
$ pip install -e .
```

## W2: Download Data

In order to do a fresh download of all the data that we use in CLICS⁴, you need to run the following command:

```
$ cldfbench download lexibank_clics4.py
```

## W3: Create CLICS4 Dataset

Before you can run the code, you must make sure to have downloaded all data and also obtained actual copies of Glottolog, Concepticon, and CLTS. An easy way to obtain these with the help of `cldfbench` is to run the command `cldfbench catconfig` and follow instructions there. If you use a Windows machine, you will need some additional preparations (see [Snee 2024](https://calc.hypotheses.org/7852)), so we kindly ask you to follow the respective instructions in Snee (2024).

If you have successfully run the `catconfig` subcommand, just type:

```
$ cldfbench lexibank.makecldf --glottolog-version=v5.1 --concepticon-version=v3.3.0 --clts-version=v2.3.0 lexibank_clics4.py
```

In the other case, specify the explicit locations of the repositories for Glottolog, Concepticon, and CLTS as follwo.

```
cldfbench lexibank.makecldf --glottolog-repos=Path2Glottolog --concepticon-repos=Path2Concepticon --clts-repos=Path2Clics --glottolog-version=v5.1 --concepticon-version=v3.3.0 --clts-version=v2.3.0 lexibank_clics4.py
```

## W4: What needs to be done before we publish CLICS4 as Version 1.0

This release is a CLICS⁴ dataset that we consider generally good enough with respect to the data to be used in publications (small errors would always be possible with such large numbers of data aggregated from different sources). However, we emphasize that there are a couple of shortcomings for now that we will try to handle before publishing a new version of CLICS that succeeds the current version 3.0 at https://clics.clld.org. Before publishing this new CLLD version of CLICS⁴, we will implement a new representation of the data in order to adhere to the representation of ParameterNetworks in the new [CLDF specification](https://cldf.clld.org).  



## Statistics


![Glottolog: 100%](https://img.shields.io/badge/Glottolog-100%25-brightgreen.svg "Glottolog: 100%")
![Concepticon: 100%](https://img.shields.io/badge/Concepticon-100%25-brightgreen.svg "Concepticon: 100%")
![Source: 100%](https://img.shields.io/badge/Source-100%25-brightgreen.svg "Source: 100%")
![BIPA: 100%](https://img.shields.io/badge/BIPA-100%25-brightgreen.svg "BIPA: 100%")
![CLTS SoundClass: 100%](https://img.shields.io/badge/CLTS%20SoundClass-100%25-brightgreen.svg "CLTS SoundClass: 100%")

- **Varieties:** 3,420 (linked to 2,149 different Glottocodes)
- **Concepts:** 1,730 (linked to 1,730 different Concepticon concept sets)
- **Lexemes:** 1,443,325
- **Sources:** 94
- **Synonymy:** 1.10
- **Invalid lexemes:** 0
- **Tokens:** 8,107,217
- **Segments:** 2,034 (0 BIPA errors, 0 CLTS sound class errors, 2026 CLTS modified)
- **Inventory size (avg):** 40.74

## Possible Improvements:

- Languages linked to [bookkeeping languoids in Glottolog](http://glottolog.org/glottolog/glottologinformation#bookkeepinglanguoids):
  - Laisaw Thu Htay Kung [lait1239](http://glottolog.org/resource/languoid/id/lait1239)
  - Songlai-Hettui 8Karchaung (Hettui) [song1313](http://glottolog.org/resource/languoid/id/song1313)
  - Songlai-Maung Um (Song) 1Maung Um (Song) [song1313](http://glottolog.org/resource/languoid/id/song1313)
  - Laitu (Khuasung) [lait1239](http://glottolog.org/resource/languoid/id/lait1239)
  - Doitu (Hetsawlay) [song1313](http://glottolog.org/resource/languoid/id/song1313)
  - Thaiphum (Rengkheng) [thai1262](http://glottolog.org/resource/languoid/id/thai1262)
  - Laitu Ahongdong [lait1239](http://glottolog.org/resource/languoid/id/lait1239)
  - Taungtha (Wethet) [rung1263](http://glottolog.org/resource/languoid/id/rung1263)
  - Khalaj [khal1270](http://glottolog.org/resource/languoid/id/khal1270)



# Contributors

Name               | GitHub user | Description | Role
---                | ---         | --- | --- 
Annika Tjuka | @annikatjuka | maintainer | Author
Christoph Rzymski   | @chrzyki         | maintainer   | Author
Robert Forkel | @xrotwang | maintainer | Author
Johann-Mattis List | @LinguList  | maintainer | Author






## CLDF Datasets

The following CLDF datasets are available in [cldf](cldf):

- CLDF [Wordlist](https://github.com/cldf/cldf/tree/master/modules/Wordlist) at [cldf/Wordlist-metadata.json](cldf/Wordlist-metadata.json)
- CLDF [StructureDataset](https://github.com/cldf/cldf/tree/master/modules/StructureDataset) at [cldf/StructureDataset-metadata.json](cldf/StructureDataset-metadata.json)