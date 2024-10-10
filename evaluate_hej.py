from re import split
import os
import json
import jsonlines
import os
import argparse
from sympy import false
import sys
sys.path.append('main')
import subprocess
import re

lang2file = {"C": "c", "Java":"java", "Python": "py"}

human_eval_loc_path = ''
human_eval_loc = {}
with open(human_eval_loc_path, 'r') as f:
    loc_str = f.read()
locs = loc_str.split('\n')
for x in locs:
    if x == '':
        break
    human_eval_loc[x.split(' ')[0]] = [(int)(x.split(' ')[-1].split('-')[0]),(int)(x.split(' ')[-1].split('-')[1])]


def formulate_code(lang, _input, remove_comment=False, input_is_file=True):
    if input_is_file:
        with open(_input) as rf:
            code = rf.read()
    else: code = _input
    with open("tmp."+lang2file[lang], "w") as wf:
        if remove_comment:
            wf.write(comment_remover(code, lang))
        else:
            wf.write(code)
    
    if lang in ["C", "Java"]:
        with open("tmp."+lang2file[lang]) as f:
            out = subprocess.run("clang-format -style=file", 
                        stdin=f, 
                        stdout=subprocess.PIPE, 
                        stderr=subprocess.PIPE,
                        timeout=10,
                        shell=True).stdout.decode("utf-8")
    elif lang == "Python":
        subprocess.run(f"python -m black -S tmp.py",
                        stderr=subprocess.PIPE,
                        timeout=10,
                        shell=True)
        with open("tmp.py") as rf:
            out = rf.read()
    os.remove("tmp."+lang2file[lang])
    return "\n".join([o.rstrip() for o in out.splitlines() if len(o.rstrip()) > 0])


def comment_remover(code, lang):
    if lang in ["C", "Java"]:
        code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
        code = re.sub(r'//.*', '', code)
        code = re.sub(r'^\s*$', '', code, flags=re.MULTILINE) #Remove empty lines
        return code 
    if lang == "Python":
        code = re.sub(r'\'\'\'.*?\'\'\'', '', code, flags=re.DOTALL)
        code = re.sub(r'#.*', '', code)
        code = re.sub(r'^\s*$', '', code, flags=re.MULTILINE) #Remove empty lines
        return code 
    

def load_human_eval(main_dir, test_file, remove_comment_flag=True, first_round=False):
    code = ''
    with open(os.path.join(main_dir, 'src/main/java/humaneval/buggy', test_file + '.java'), 'r') as f:
        code = f.read()
    if first_round:
        with open('tmp.java', 'w') as f:
            f.write(code)
        codes = code.split('\n')
        location = human_eval_loc[test_file]
        tmp_lines = []
        for strat_loc in range(location[0], location[1]):
            tmp_lines.append(codes[strat_loc - 1]) 
        code = '\n'.join(codes)
        if remove_comment_flag:
            code = comment_remover(code, 'Java')
        codes = code.split('\n')
        for index, x in enumerate(codes):
            if x in tmp_lines:
                codes[index] = x + ' //buggy line(s)'
        code = '\n'.join(codes)
    with open(os.path.join(main_dir, 'src/main/java/humaneval/buggy', test_file + '.java'), 'w') as f:
        f.write(code)
    return code


def count_passed_and_failed(text):
    pattern_failed = re.compile(r'(\d+)\sfailed')
    pattern_passed = re.compile(r'(\d+)\spassed')

    match_failed = pattern_failed.search(text)
    match_passed = pattern_passed.search(text)

    num_failed = None
    num_passed = None

    if match_failed:
        num_failed = int(match_failed.group(1))
    if match_passed:
        num_passed = int(match_passed.group(1))

    return num_failed, num_passed


def checkout_test_bip(err_repo):
    test_cases = []
    if 'ERROR' in err_repo:
        return [err_repo], False
    if 'invalid syntax' in err_repo:
        return [err_repo], False
    if 'failed' in err_repo:
        return [err_repo], False
    if "FAILED" in err_repo or 'error' in err_repo:
        return [err_repo], False
    pattern = re.compile(r'=================================== FAILURES ===================================(.*)', re.DOTALL)
    match = pattern.search(err_repo)
    if match:
        return [x for x in match.groups()], False
    return test_cases, True
                

def parseHumanEvalTestCases(err_repo):
    flags = True
    test_cases = []
    if 'There are test failure' in err_repo:
        flags = False
        pattern = re.compile(r'test_\d+\(humaneval\..*?\)(.*?)\n\n', re.DOTALL)
        matches = pattern.findall(err_repo)
        for m in matches:
            test_cases.append(m)
        return test_cases, flags
    return test_cases, flags


class HumanEvalTestCase:
    def __init__(self, test_folder, test_file):
        self.test_folder = test_folder
        self.test_cases = []
        self.test_file = test_file
        
    def run_test(self):
        run_cmd = 'mvn test -Dtest=TEST_' + self.test_file
        try:
            return subprocess.run(run_cmd, 
                                  shell=True,
                                  text=True,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE,
                                  cwd=self.test_folder).stdout
        except subprocess.TimeoutExpired:
            return 'Compile Timeout'
    

class BipTestCase:
    def __init__(self,
                 test_folder):
        self.test_folder = test_folder
        self.test_cases = []
        
    def run_test(self):
        run_cmd = 'bugsinpy-test'
        env = os.environ.copy()
        env['PATH'] = env['PATH']+ ''
        try:
            return subprocess.run(run_cmd, 
                                  shell=True,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE,
                                  text=True,
                                  env=env,
                                  cwd=self.test_folder).stdout
        except  subprocess.TimeoutExpired:
            return 'Compile Timeout'
        
    def getTestCases(self, errmessage):
        pass
        
           
class Prompt:
    def __init__(self,
                 main_dir,
                 lang,
                 bug_id,
                 test_case_obj,
                 benchmark = 'bugsinpy',
                 program_type = 'raw',
                 check_file = 'store_code.py',
                 first_round = True,
                 extra = False,
                 max_token=4000) -> None:
        self.main_dir = main_dir
        self.test_case_obj = test_case_obj
        self.bug_id = bug_id
        self.extra = extra
        if first_round:
            self.check_file = 'store_code.py'
        else:
            self.check_file = check_file
        self.program_type = program_type
        self.max_token = max_token
        self.benchmark = 'bugsinpy'
        self.benchmark = benchmark
        self.first_round = first_round
        self.lang = lang
        self._get_program()
        if len(self.program) // 2 > self.max_token:
            raise UserWarning(f'The program of {self.bug_id} is too long!')
        self.test_cacses = self._get_falling_test_case()
        
    def _get_program(self):
        if self.benchmark in ['human-eval', 'bugsinpy']:
            if self.benchmark == 'bugsinpy':
                self.program = f"```\n"
                if self.program_type == "raw":
                    self.program += formulate_code(self.lang, remove_comment = False, input_is_file=True,
                                                _input=os.path.join(self.main_dir, self.bug_id, self.check_file)
                                                )+"\n```"
                elif self.program_type == 'empty':
                    self.program = ''
                return
            if self.benchmark == 'human-eval':
                self.program = f"```\n"
                if self.program_type == "raw":
                    self.program += load_human_eval(main_dir=self.main_dir,test_file=self.bug_id, first_round=(self.first_round)) +"\n```"
                return
        raise UserWarning(f'The benchmark{self.benchmark} is not supported in the framework.')
            
    def _get_falling_test_case(self):
        if self.benchmark in ['human-eval', 'bugsinpy']:
            if self.benchmark == 'bugsinpy':
                output_err_info = self.test_case_obj.run_test()
                test_cases, flags = checkout_test_bip(output_err_info)
                if flags:
                    return []
                else:
                    return [output_err_info]
                
            elif self.benchmark == 'human-eval':
                output_err_info = self.test_case_obj.run_test()
                test_cases, flags = parseHumanEvalTestCases(output_err_info)
                if flags:
                    return []
                else:
                    return test_cases
        raise UserWarning(f'The benchmark{self.benchmark} is not supported in the framework.')
        
    def getPromptInfo(self):
        if not self.extra:
            return self.program
        
        if self.benchmark == 'bugsinpy':
            prompt = self.program
            if (len(prompt) + len('\nTest infomation:\n') + len(self.test_cacses[0])) // 2 + 1 < self.max_token:
                can_input_num = self.max_token - len(prompt) - len('\nTest infomation:\n') 
                prompt = prompt + '\nTest infomation:\n' + self.test_cacses[0][0:can_input_num * 2]
                return prompt
            else:
                return prompt
        
        prompt = self.program
        for index, x in enumerate(self.test_cacses):
            if ((len(prompt) + len(f'\nTestCase{index}:\n') + len(x))) // 2 + 1 < self.max_token:
                prompt = prompt + f'\nTestCase{index}' + x + '\n'
        
        return prompt

    def feedback(self, code):
        with open(os.path.join(self.main_dir, 'src/main/java/humaneval/buggy', self.bug_id + '.java'), 'w') as f:
            f.write(code)

parser = argparse.ArgumentParser(description='Make Eval')
parser.add_argument('-pat', type=str, help='patches generated')
parser.add_argument('-human_eval_dir', type=str, help='folder for human eval')
parser.add_argument('-result', type=str, help='output result')
args = parser.parse_args()

test_human_eval_dir = args.human_eval_dir
result_txt = args.result
srepair_eval_json = args.pat

js  = []


with open(srepair_eval_json, 'r') as f:
    for item in jsonlines.Reader(f):
        js.append(item)


if __name__ == '__main__':
    for x in js:
        bug_id = x['task_id']
        # bug_id = x
        print(f'repairing {bug_id}...')
        old_code = ''
        # new_codes = js[bug_id]['patches'][0]
        new_codes = x['fix_new']
        
        new_codes = new_codes.replace(r'```java\n', '')
        new_codes = new_codes.replace(r'```', '')
        new_codes = new_codes.replace(r'humaneval.fixed', 'humaneval.buggy')
        
        
        with open(os.path.join(test_human_eval_dir, 'src/main/java/humaneval/buggy', bug_id + '.java'), 'r') as f:
            old_code =f.read()
        flags = False
        new_code = new_codes.split('\n')
        # new_code = [x for x in new_code if x != '' and x != '\n']
        # new_code[0] = 'package humaneval.buggy;'
        new_code = '\n'.join(new_code)
        with open(os.path.join(test_human_eval_dir, 'src/main/java/humaneval/buggy', bug_id + '.java'), 'w') as f:
            f.write(new_code)
        testcase = HumanEvalTestCase('', bug_id)
        test_cases, flags = parseHumanEvalTestCases(testcase.run_test())
        if flags:
            with open(result_txt, 'a+') as fz:
                fz.write(f'{bug_id} SUCCESSED\n')
        with open(os.path.join(test_human_eval_dir, 'src/main/java/humaneval/buggy', bug_id + '.java'), 'w') as f:
             f.write(old_code)
        if flags:
            continue
        with open(result_txt, 'a+') as fz:
            fz.write(f'{bug_id} FAILED\n')
