import difflib
from email import message
import json, os, random
import numpy as np
from sympy import true
from tqdm import tqdm
from openai import OpenAI

# 为了提供给JavaTransformer工具，JavaTransformer只能转换.java文件
def write_d4j1_2java(json_file_path, written_path):
  with open(json_file_path, 'r') as f:
    d4j_sf_data = json.load(f)

  for item in d4j_sf_data:
    # str，需要写入.java文件才能被JavaTransformer处理
    buggy_function = d4j_sf_data[item]["buggy"]
    bug_name = item

    if not os.path.exists(os.path.join(written_path, bug_name)):
      os.system('mkdir -p {}'.format(os.path.join(written_path, bug_name)))

    with open(os.path.join(written_path, bug_name, bug_name+".java"), 'w') as writer:
      writer.write(buggy_function)

def write_d4j2_2java(json_file_path, written_path):
  with open(json_file_path, 'r') as f:
    d4j_mf_data = json.load(f)

  for item in d4j_mf_data:
    for i, function_dict in enumerate(d4j_mf_data[item]["functions"]):
      fixed_function = function_dict["fixed_function"]
      buggy_function = function_dict["buggy_function"]
      bug_name = item

      if not os.path.exists(os.path.join(written_path, bug_name)):
        os.system('mkdir -p {}'.format(os.path.join(written_path, bug_name)))

      # print(bug_name, i, type(fixed_function))
      with open(os.path.join(written_path, bug_name, bug_name + "_" + str(i) + ".java"), 'w') as writer:
        writer.write(buggy_function)

# 将JavaTransformer转变后的内容写入json
def calculate_num_transfrom_d4j1(src_path, bench_path, written_path):
  transform_type = sorted(os.listdir(src_path))
  # print(transform_type)
  
  with open(bench_path, 'r') as f:
    bench_data = json.load(f)
  
  json_file = {}
  
  for bug_name in bench_data:
    json_file[bug_name] = {}
    for type in transform_type:
      
      json_file[bug_name][type] = []
      
      if os.path.exists(os.path.join(src_path, type, bug_name)):
        for transform_file_path in os.listdir(os.path.join(src_path, type, bug_name)):
          # print(transform_file_path)
          with open(os.path.join(src_path, type, bug_name, transform_file_path), 'r') as reader:
            transform_function = reader.read()
          json_file[bug_name][type].append(transform_function)
    
    with open(written_path, 'w') as f:
      json.dump(json_file, f, indent=2)

def calculate_num_transfrom_d4j2(src_path, bench_path, written_path):
  transform_type = sorted(os.listdir(src_path))
  # print(transform_type)
  
  with open(bench_path, 'r') as f:
    bench_data = json.load(f)
  
  json_file = {}
  
  for bug_name in bench_data:
    json_file[bug_name] = {}
    json_file[bug_name]["function_num"] = bench_data[bug_name]["function_num"]
    n = bench_data[bug_name]["function_num"]
    
    json_file[bug_name]["functions"] = [{} for _ in range(n)]
    
    for type in transform_type:
      
      for i in range(n):
        json_file[bug_name]["functions"][i][type] = []
      
      
      if os.path.exists(os.path.join(src_path, type, "multi_functions", bug_name)):
        for transform_file_path in os.listdir(os.path.join(src_path, type, "multi_functions", bug_name)):
          
          with open(os.path.join(src_path, type, "multi_functions", bug_name, transform_file_path), 'r') as reader:
            transform_function = reader.read()
            
          idx = int(transform_file_path.split("_")[1])
          
          json_file[bug_name]["functions"][idx][type].append(transform_function)
          
    with open(written_path, 'w') as f:
      json.dump(json_file, f, indent=2)

###################################################### random 选取变体 ######################################################
# 从上述json中随机抽取一个变体       
def ranmdom_construct_d4j1(transform_d4j_sf_path):
  d4j_sf_random = {}
  
  with open(transform_d4j_sf_path, 'r') as f:
    transform_d4j_data = json.load(f)
    
  for item in transform_d4j_data:
    
    transform_functions = []
    
    for transform_type in transform_d4j_data[item]:
      
      if transform_d4j_data[item][transform_type] != []:
        for function in transform_d4j_data[item][transform_type]:
          
          transform_functions.append((function, transform_type))
    if transform_functions == []:
      # print(item)
      d4j_sf_random[item] = {}
    else:
      random_function = random.choice(transform_functions)
      d4j_sf_random[item] = {
        "buggy": random_function[0],
        "type": random_function[1]
      }
  
  return d4j_sf_random    

def ranmdom_construct_d4j2(transform_d4j_mf_path):
  d4j_mf_random = {}
  
  with open(transform_d4j_mf_path, 'r') as f:
    transform_d4j_data = json.load(f)
    
  for item in transform_d4j_data:
    d4j_mf_random[item] = {}
    d4j_mf_random[item]["function_num"] = transform_d4j_data[item]["function_num"]
    d4j_mf_random[item]["functions"] = []
    for idx in range(int(transform_d4j_data[item]["function_num"])):
      function_list = []
      for type in transform_d4j_data[item]["functions"][idx]:
        if transform_d4j_data[item]["functions"][idx][type] != []:
          for function in transform_d4j_data[item]["functions"][idx][type]:
            function_list.append((function, type))
      
      if function_list:
        random_function = random.choice(function_list)
        d4j_mf_random[item]["functions"].append(random_function)
      else:
        d4j_mf_random[item]["functions"].append([])
        # print(item, idx)
  
  return d4j_mf_random

# ReorderCondition: 交换顺序 变
# VariableRenaming: 修改局部变量名 改
# UnusedStatement: 额外增加不会被执行的判断语句 加
  

if __name__ == '__main__':
  
  pass