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
Step2. Test Report Prompe
```bash
python -m gptcode.cli ask_repair --ds dataset_name --lang code_language
```
Step3. Refined prompt
```bash
python -m gptcode.cli ask_repair --ds dataset_name --lang code_language 
```



## Results


## Contributing
If you would like to contribute to the project, please open an issue or submit a pull request.

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
