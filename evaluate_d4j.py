import subprocess
import argparse
import json
import os


CMD_TIME = 300


def getCheckOutCMD(project, bug_id, target_dir):
    """ 
    Args:
        bug_id (str): bug_id
        target_dir (str): target_dir to checkout
    """
    # check_dir = os.path.join(target_dir, project+"-"+bug_id)
    return f'defects4j checkout -p {project} -v {bug_id}b -w {target_dir}'


def getCompileCMD():
    return 'defects4j compile'


def getTestCMD():
    return 'defects4j test'


def runCMD(cmd, cwd=None):
    try:
      res = subprocess.run(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout= CMD_TIME,
        cwd=cwd)
      return res.stderr + '\n' + res.stdout
    except  subprocess.TimeoutExpired:
      return 'Timeout'
    
parser = argparse.ArgumentParser(description='Make Eval')
parser.add_argument('-loc', type=str, help='location of buggy function place')
parser.add_argument('-out', type=str, help='out put json path')
parser.add_argument('-pat', type=str, help='patches json path')
parser.add_argument('-tmp', type=str)
args = parser.parse_args()


def evalResult(err, type='test'):
    if type == 'test':
      result = err
      result = result.split("\n")
      if result[-1].endswith("OK"):
        return True
      result = list(filter(None, result))
      for i in range(len(result)):
        if(result[i].startswith("Failing tests:")):
          if "Failing tests: 0" in result[i]:
            return True
          else:
            return False
      return True
    else:
      if 'Compilation failed' in err:
        return False
      result = err
      result = result.split("\n")
      result = list(filter(None, result))
      for line in result:
        if(not line.endswith("OK")):
          return False
      return True


def insertData(old_codes, locations, functions):
    old_lines = old_codes.split('\n')
    result_lines = []
    start_index = 0
    for function, location in zip(functions, locations):
        result_lines = result_lines + old_lines[start_index: location[0] - 1]
        result_lines = result_lines + function.split('\n')
        start_index = location[1]
    result_lines = result_lines + old_lines[start_index: -1]
    new_code = "\n".join(result_lines)
    return new_code


def run_eval(to_be_eval, location_dict, tmp_folder):
    to_be_store = {}
    for project_id in to_be_eval.keys():
        to_be_store[project_id] = {}
        prject, bug_id = project_id.split('-')
        
        patches = to_be_eval[project_id]['patches']
        for patch in patches:

          # Start checking out
          status = runCMD(getCheckOutCMD(prject, bug_id=bug_id, target_dir=tmp_folder))
          if status == 'Timeout':
            to_be_store[project_id]['Test'] = 'Check out Timeout'
            # print(f"{project_id} Check out Timeout")
            continue

          patch = [patch]
          locations = [[location_dict[project_id]['start'], location_dict[project_id]['end']]]
          old_codes = ""
          file_path = location_dict[project_id]['loc']
          try:
            with open(os.path.join(tmp_folder, file_path), 'r', encoding='utf-8') as f:
                old_codes = f.read()
          except:
            to_be_store[project_id]['Test'] = 'Check out Failed'
            # print(f"{project_id} Check out Failed")
            break
          new_codes = insertData(old_codes=old_codes, locations=locations, functions=patch)
          with open(os.path.join(tmp_folder, file_path), 'w') as f:
              f.write(new_codes)

          # Start compile 
          status = runCMD(getCompileCMD(), cwd=tmp_folder)
          if status == 'Timeout':
              to_be_store[project_id]['Test'] = 'Compile Timeout'
              # print(f"{project_id} Compile Timeout")
              continue
          elif not evalResult(status, 'compilation'):
              to_be_store[project_id]['Test'] = 'Compile Failed'
              # print(f"{project_id} Compile Failed")
              continue
          
          # Start test
          status = runCMD(getTestCMD(), cwd=tmp_folder)
          if status == 'Timeout':
              to_be_store[project_id]['Test'] = 'Test Timeout'
              # print(f"{project_id} Test Timeout")
              continue
          if evalResult(status):
              to_be_store[project_id]['Test'] = 'Plausible'
              to_be_store[project_id]['patch'] = patch
              break
          else:
              to_be_store[project_id]['Test'] = 'Incorrect'
    return to_be_store


def run_eval_multi(to_be_eval, location_dict, tmp_folder):
  to_be_store = {}
  for project_id in to_be_eval.keys():
    to_be_store[project_id] = {}
    prject, bug_id = project_id.split('-')
  
  patches = to_be_eval[project_id]['patches']
  for patch in patches:
    status = runCMD(getCheckOutCMD(prject, bug_id=bug_id, target_dir=tmp_folder))
    if status == 'Timeout':
      to_be_store[project_id]['Test'] = 'Check out Timeout'
      continue

    file_path = location_dict[project_id]["functions"][0]["path"]
    try:
      with open(os.path.join(tmp_folder, file_path), 'r', encoding='utf-8') as f:
        old_codes = f.read() 
    except:
      to_be_store[project_id]['Test'] = 'Check out Failed'
      break
    patch_mf = []
    locations = []
    for idx in patch:
      patch_mf.append(patch[idx])
      locations.append([location_dict["functions"][idx]["start_loc"], location_dict["functions"][idx]["end_loc"]])
    new_codes = insertData(old_codes=old_codes, locations=locations, functions=patch)
    with open(os.path.join(tmp_folder, file_path), 'w') as f:
      f.write(new_codes)

    # Start compile  
    status = runCMD(getCompileCMD(), cwd=tmp_folder)
    if status == 'Timeout':
        to_be_store[project_id]['Test'] = 'Compile Timeout'
        continue
    elif not evalResult(status, 'compilation'):
        to_be_store[project_id]['Test'] = 'Compile Failed'
        continue
    
    # Start test
    status = runCMD(getTestCMD(), cwd=tmp_folder)
    if status == 'Timeout':
        to_be_store[project_id]['Test'] = 'Test Timeout'
        continue
    if evalResult(status):
        to_be_store[project_id]['Test'] = 'Plausible'
        to_be_store[project_id]['patch'] = patch
        break
    else:
        to_be_store[project_id]['Test'] = 'Incorrect'
  return to_be_store




if __name__ == '__main__':
    
    result_dict = {}
    patch_json_path = args.pat
    output_path = args.out
    location_json = args.loc
    tmp_folder = args.tmp
    
    if not os.path.exists(patch_json_path) or not os.path.exists(output_path) or not os.path.exists(location_json) or not os.path.exists(tmp_folder):
        print('Bad Folder here ....')
    
    with open(patch_json_path, 'r') as f:
        to_be_eval = json.load(f)
        
    with open(location_json, 'r') as f:
        location_dict = json.load(f)
        
    result_dict = run_eval(to_be_eval, location_dict, tmp_folder)
    
    with open(output_path, 'w') as f:
        json.dump(result_dict, f, indent=2)