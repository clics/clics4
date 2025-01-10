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
