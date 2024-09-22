[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)


# NeurIPS - Ariel Data Challenge (ADC) 2024

## Description

> This GitHub repository contains all of my work as a participant in the Kaggle NeurIPS - Ariel Data Challenge 2024 competition.
>
>NeurIPS - Ariel Data Challenge 2024 aims to develop models capable of extracting weak signals from exoplanets using simulated data from the ESA's future Ariel mission. Participants are required to build supervised learning models to tackle this astronomical data analysis challenge.

## Objectives

- Extract atmospheric spectra of exoplanets from noisy data.
- Estimate the uncertainties associated with the predicted spectra for each wavelength.

## Problem

Exoplanet signals are corrupted by noise, particularly "jitter noise" making it difficult to accurately extract atmospheric spectra.

## Expected Results

- Extraction of spectra with good alignment compared to real data.
- Estimation of the uncertainties associated with the predictions (the predicted wavelengths).

# Installation for developpement

To install this project you need these dependencies installed:

- Python `">=3.10,<3.11"`
- [Poetry](https://python-poetry.org/docs/) `1.8.3`

### Clone the project

```sh
git clone https://www.github.com/CedrickArmel/neurips_adc.git
```

### Install the dependencies

```sh
poetry shell && poetry instal
```

## Project Organization

```md

├── data
│   ├── external       <- Data from third party sources.
│   ├── interim        <- Intermediate data that has been transformed.
│   ├── processed      <- The final, canonical data sets for modeling.
│   └── raw            <- The original, immutable data dump.
│
├── models             <- Trained and serialized models, model predictions, or model summaries
│
├── notebooks          <- Jupyter notebooks. Naming convention is a number (for ordering),
│                         the creator's initials, and a short `-` delimited description, e.g.
│                         `1.0-jqp-initial-data-exploration`.
│
├── pyproject.toml     <- Project configuration file with package metadata for
│                         neuripsadc and configuration for tools like black
│
├── references         <- Data dictionaries, manuals, and all other explanatory materials.
│
├── reports            <- Generated analysis as HTML, PDF, LaTeX, etc.
│   └── figures        <- Generated graphics and figures to be used in reporting
│
├── poetry.lock   <- resolves and locks all dependencies and their sub-dependencies in the pyproject.toml file.
│
│
└── neuripsadc   <- Source code for use in this project.
    │
    ├── __init__.py             <- Makes neuripsadc a Python module
```

--------
