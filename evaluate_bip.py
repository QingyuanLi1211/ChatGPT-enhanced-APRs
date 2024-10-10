import re
import json
import os
import subprocess
import argparse

location_dict = {}
to_be_evaled = {}

parser = argparse.ArgumentParser(description='Make Eval')
parser.add_argument('-loc', type=str, help='location of buggy function place')
parser.add_argument('-out', type=str, help='out put json path')
parser.add_argument('-pat', type=str, help='patches json path')
parser.add_argument('-bip_folder', type=str)
args = parser.parse_args()

eval_data = args.pat
location_path = args.loc
test_root = args.bip_folder
test_result_root = args.out


with open(location_path, 'r') as f:
    location_dict = json.load(f)
with open(eval_data, 'r') as f:
    to_be_evaled = json.load(f)

class BipTestCase:
  def __init__(self,
                test_folder):
    self.test_folder = test_folder
    self.test_cases = []
      
  def run_test(self):
    run_cmd = 'bugsinpy-test'
    env = os.environ.copy()
    env['PATH'] = env['PATH']+ ':'
    try:
        return subprocess.run(run_cmd, 
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                timeout= 3,
                cwd=self.test_folder).stdout
    except  subprocess.TimeoutExpired:
        return 'Compile Timeout'

def check_if_passed(bug_id):
  project_name = bug_id.split('-')
  project_name.pop()
  project_name = '-'.join(project_name)
  path = os.path.join(test_root, bug_id, project_name)
  bip_test = BipTestCase(path)
  err_repo = bip_test.run_test()
  return check_bip_error(err_repo), err_repo

def trans_key_2_path(key):
  lst = key.split(r"/")
  lst[0], lst[1] = lst[1], lst[0]
  if '-' in lst[-1]:
      lst[-1] = lst[-1].split("-")[0] + '.py'
  return  lst[0], r'/'.join(lst)

def check_patch(patch, key):
  bug_id, path  = trans_key_2_path(key)
  flag = False
  loc1, loc2 = location_dict[key][0], location_dict[key][1]
  if not check_bip_if_func(patch):
      return False
  with open(os.path.join(test_root, path), 'r') as f:
      old_code = f.read()    
      old_code_lines = old_code.split('\n')
      pre_codes = old_code_lines[0 : loc1]
      post_codes = old_code_lines[loc2 + 1 : -1]
      base_line = old_code_lines[loc1]
      rouf_len = len(base_line) - len(base_line.lstrip())
      new_codes = [' ' * rouf_len + x for x in patch.split('\n')]
      new_codes = pre_codes + new_codes + post_codes
      new_code = '\n'.join(new_codes)    
      with open(os.path.join(test_root, path), 'w') as f:
          f.write(new_code)
      flag, err_repo = check_if_passed(bug_id)
      with open(os.path.join(test_root, path), 'w') as f:
          f.write(old_code)
      return flag, err_repo
            
def run():
  for key in to_be_evaled.keys():
    bug_id, path  = trans_key_2_path(key)
    flag = False
    for patch in to_be_evaled[key]['patches']:
      loc1, loc2 = location_dict[key][0], location_dict[key][1]
      patch = patch.strip()
      if not check_bip_if_func(patch):
          continue
      with open(os.path.join(test_root, path), 'r') as f:
          old_code = f.read()
      old_code_lines = old_code.split('\n')
      pre_codes = old_code_lines[0 : loc1]
      post_codes = old_code_lines[loc2 + 1 : -1]
      base_line = old_code_lines[loc1]
      rouf_len = len(base_line) - len(base_line.lstrip())
      new_codes = [' ' * rouf_len + x for x in patch.split('\n')]
      new_codes = pre_codes + new_codes + post_codes
      new_code = '\n'.join(new_codes)
      with open(os.path.join(test_root, path), 'w') as f:
          f.write(new_code)
      flag, err_repo = check_if_passed(bug_id)
      with open(os.path.join(test_root, path), 'w') as f:
          f.write(old_code) 
      if flag:
          with open(os.path.join(repo_duc, f"{'-'.join(key.split('/'))}-err.txt"), 'a+') as f:
              f.write(err_repo)
          break
    with open(test_result_root, 'a+') as f:
        con_txt = f"{key} SUCCESSED\n" if flag else f"{key} FAILED\n"
        f.write(con_txt)

lang2comm = {"Java": "//", "C": "//", "Python": "#"}

def check_bip_error(test_msg):
  if 'fail' in test_msg or 'FAIL' in test_msg or 'EOF' in test_msg:
      return False
  elif 'error' in test_msg or 'Error' in test_msg:
      return False
  elif 'ERROR' in test_msg or 'invalid syntax' in test_msg:
      return False
  elif 'Timeout' in test_msg:
      return False
  return True


def check_bip_if_func(code):
  pattern = re.compile(r'^\s*def\s+\w+\s*\(.*\)\s*:', re.MULTILINE)
  return bool(pattern.search(code))


def extract_buggy_lines(code: str, lang="C") -> list[str]:
  res = []
  code_lines = code.splitlines()
  for i, l in enumerate(code_lines):
      if lang2comm[lang] in l and "buggy" in l.lower():
          if len(l.split(lang2comm[lang])[0].strip()) > 0:
              res.append(l.split(lang2comm[lang])[0].strip())
          elif i+1 < len(code_lines):
              res.append(code_lines[i+1].strip())
  return res

class ParseError(Exception):
  def __init__(self, message, status):
      super().__init__(message, status)
      self.message = message
      self.status = status


def parse_code(response, role, lang="C"):   
  import re
  code_lst = []
  for i, pattern in enumerate([r'```(?:[^\n]*\n)?(.*?)```', r'```(?:[^\n]*\n)?(.*?)\$\$', r'`(?:[^\n]*\n)?(.*?)`', r'```(?:[^\n]*\n)?(.*?)$']):
      code_lst = re.findall(pattern, response, re.DOTALL)
      if len(code_lst) > 0 and len(code_lst[0]) > 0:
          break
  if len(code_lst) == 0: #Cannot find valid code
      logging.error("Cannot extract any code")
      raise ValueError("Cannot extract any code")
  
  if role in ["fixer", "developer"]:
      code = code_lst[-1].strip()
  else:
      code = "\n".join([c.strip() for c in code_lst])
  if "$" in code:
      code = code[:code.find("$")].strip()
  
  exp_lst = []
  for pattern in [r'\$\$(?:[^\n]*\n)?(.*?)\$\$', r'\$\$(?:[^\n]*\n)?(.*?)$', r'^(?:[^\n]*\n)?(.*?)```']:
      exp_lst = re.findall(pattern, response, re.DOTALL)
      if len(exp_lst) > 0: break

  if len(exp_lst) == 0:
      logging.warning("This response doesn't explain the repairing")
      explaination = ""
  else:
      explaination = "\n".join(exp_lst)
  if role in ['bip-fixer']:
      return {"code": code, "explaination": explaination}
  if role in ["fixer", "developer"]:
      return {"code": code, "explaination": explaination}
  if role == "localizer":
      return {"labeled_code": code, "explaination": explaination, "buggy_line": extract_buggy_lines(code, lang)}
  raise ValueError(f"Not identified role {role} during parsing code!")


def cal_token(*args):
  lenth = 0
  for v in args:
      if isinstance(v, int):
          lenth += v * 2
      elif isinstance(v, str):
          lenth += len(v)
      elif isinstance(v, list) and isinstance(v[0], dict):
          lenth += sum([len(vd["content"]) for vd in v])
  return lenth // 2




if __name__ == '__main__':
    run()
