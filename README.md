# CLICS⁴

## How to cite

If you use these data please cite
this dataset using the DOI of the [particular released version](../../releases/) you were using

## Description


This dataset is licensed under a CC-BY-4.0 license

## Notes

# Workflow Instructions

To run the code, you need to follow specific workflow instructions

## 1 Install Packages

- glottolog
- concepticon
- clts

Install pyclics (manually for now):

```
$ git clone https://github.com/clics/pyclics.git
$ git checkout colexifications
$ pip install -e .
```

## 2 Download Data

```
cldfbench download lexibank_clics4.py
```

## 3 Create CLICS4 Dataset

```
cldfbench lexibank.makecldf --glottolog-repos=Path2Glottolog --concepticon-repos=Path2Concepticon --clts-repos=Path2Clics --glottolog-version=v4.6 --concepticon-version=v3.2.0 --clts-version=v2.3.0 lexibank_clics4.py
```

## 4 TODO

- [x] check the sources of all datasets (they must be included, contribution table)
- [ ] check all CLDF datasets, sometimes, values are missing
- [ ] publish pyclics and make an update for PyPi here (important)
- [ ] consider ignoring the similarities



## Statistics


![Glottolog: 100%](https://img.shields.io/badge/Glottolog-100%25-brightgreen.svg "Glottolog: 100%")
![Concepticon: 100%](https://img.shields.io/badge/Concepticon-100%25-brightgreen.svg "Concepticon: 100%")
![Source: 100%](https://img.shields.io/badge/Source-100%25-brightgreen.svg "Source: 100%")
![BIPA: 100%](https://img.shields.io/badge/BIPA-100%25-brightgreen.svg "BIPA: 100%")
![CLTS SoundClass: 100%](https://img.shields.io/badge/CLTS%20SoundClass-100%25-brightgreen.svg "CLTS SoundClass: 100%")

- **Varieties:** 2,638 (linked to 1,771 different Glottocodes)
- **Concepts:** 1,542 (linked to 1,542 different Concepticon concept sets)
- **Lexemes:** 1,233,912
- **Sources:** 1
- **Synonymy:** 1.11
- **Invalid lexemes:** 0
- **Tokens:** 6,979,534
- **Segments:** 1,879 (0 BIPA errors, 0 CLTS sound class errors, 1871 CLTS modified)
- **Inventory size (avg):** 41.53

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
Johann-Mattis List | @LinguList  | maintainer | Author
Annitka Tjuka | @annikatjuka | maintainer | Author
Robert Forkel | @xrotwang | maintainer | Author






## CLDF Datasets

The following CLDF datasets are available in [cldf](cldf):

- CLDF [Wordlist](https://github.com/cldf/cldf/tree/master/modules/Wordlist) at [cldf/Wordlist-metadata.json](cldf/Wordlist-metadata.json)
- CLDF [StructureDataset](https://github.com/cldf/cldf/tree/master/modules/StructureDataset) at [cldf/StructureDataset-metadata.json](cldf/StructureDataset-metadata.json)