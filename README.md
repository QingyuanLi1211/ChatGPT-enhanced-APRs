# Empirical-study-of-LLM-based-self-enhancing-APRs

## Table of Contents
- [Introduction](#introduction)
- [Installation](#installation)
- [Usage](#usage)
- [Contributing](#contributing)
- [License](#license)

## Introduction
![image](overview.png)

## Installation
In the paper, we refer to the relevant work of an article from the APR journal. The content involved is extensive, and the related environmental configuration information can be found in the `/APRS` directory.

## Datasets
Defects4J: https://github.com/rjust/defects4j

HumanEval-Java: https://github.com/ASSERT-KTH/human-eval-java

BugsInPy: https://github.com/JohnnyPeng18/TypeFix


## Usage
### 1. Refined Test Report Prompt
Step1. Repair Prompt
```bash
python -m gptcode.cli repair --ds dataset_name --lang code_language
```
Step2. Test Report Prompt
```bash
python -m gptcode.cli ask_repair --ds dataset_name --lang code_language
```
Step3. Refined Prompt
```bash
python -m gptcode.cli ask_repair --ds dataset_name --lang code_language 
```
### 2. FixAgent

We use the defualt settings for FixAgent. There are three agents useed: fixer (fix the actual code), analyzer (reasoning the code), localizer (localize the wrong code).

### 3. SRepair

Same settings as SRepair, Comment/Buggy Code, Trigger Test and Error message are extracted from datasets, which is leveraged to from Repair Suggestions. In last step, Generation model are requested to fix code.

### 4. Evaluate Datasets

#### (1) Evaluate Defects4J
```
Python evaluate_d4j.py -loc {location of buggy function place} -out {eval result json} -pat {patches json file generated in former steps} -tmp {temp folder to hold env}
```
#### (2) Evaluate HumanEval
```
Python evaluate_hej.py -pat {patches json file generated in former steps} -human_eval_dir {human eval datatset folder} -result {file to store eval result}
```

### (3) Evaluate BugsInPy
```
Python evaluate_bip.py -pat {patches json file generated in former steps} -out {out file to store result} -bip_folder {folder to hold BugsInPy environment} -loc {location file that indicates fault location in code}
```

## Results



## Contributing
If you would like to contribute to the project, please open an issue or submit a pull request.

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
