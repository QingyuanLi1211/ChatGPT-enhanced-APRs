from functools import total_ordering
from sys import prefix
from openai import OpenAI
import math, json, os, re, jsonlines

fee_client = OpenAI(
    # defaults to os.environ.get("OPENAI_API_KEY")
    api_key="yours",
    # base_url="https://api.chatanywhere.tech/v1"
)

# 删除注释
def remove_comment(text):
    pattern = re.compile(
    r"""\s*\#(?:[^\n])*| "{3}(?:\\.|[^\\])*"{3}| '{3}(?:\\.|[^\\])*'{3} | ^\s*\n""",
    re.VERBOSE | re.MULTILINE | re.DOTALL
    )
    text = re.sub(pattern, '', text)
    return re.sub(pattern, '', text)

# 删除空行
def remove_empty_line(text):
    pattern = re.compile(
    r"""^\s*\n""",
    re.VERBOSE | re.MULTILINE | re.DOTALL
    )
    return re.sub(pattern, '', text)
  
# 返回list：当n>1的情况，会有多个返回值    top_logprobs参数应该是被弃用了
def inference(messages, generation_config, model="gpt-3.5-turbo-0125"):
    try:
        # print("use free api")
        response = fee_client.chat.completions.create(
            model=model,
            messages=messages,
            # **generation_config
            max_tokens=512,
            temperature=0.95,
            top_p=0.95,
            n=10,
            logprobs=1
        )
    except Exception as e:
        try:
            # print("use fee api")
            response = fee_client.chat.completions.create(
                model=model,
                messages=messages,
                # **generation_config
                max_tokens=512,
                temperature=0.95,
                top_p=0.95,
                n=10,
                logprobs=1
            )
        except Exception as e:
            print(f"Exception in INFERENCE function {e}")
            return [], []
    outputs = [choice.message.content for choice in response.choices]

    # logprobs：对于n条生成的序列，记录每条序列的logprob_list
    logprobs = []
    
    #print(len(response.choices))
    for i, choice in enumerate(response.choices):
        try:
            #print("Single Choice: ")
            #print(choice)
            #print(choice.logprobs)
            #print(type(choice.logprobs))

            # logprob_list：对于每一条生成的序列，记录每个token的logprob的列表
            logprob_list = []
            
            for ChatCompletionTokenLogprob in choice.logprobs.content:
                # logP
                logprob = ChatCompletionTokenLogprob.logprob
                logprob_list.append(logprob)
            logprobs.append(logprob_list)

        except Exception as e:
            print('None')
            # print(choice.logprobs)

    assert len(outputs) == len(logprobs)

    # 两个长度为n的list
    return outputs, logprobs

# 计算困惑度的函数
def calculate_perplexity(sequence_logprob_list, N):
      
    sequence_logprob_sum = sum(sequence_logprob_list)
    sequence_logprob_avg = sequence_logprob_sum / N
    
    try:
      perplexity = math.exp(-sequence_logprob_avg)
    except Exception as e:
      perplexity = math.e

    return perplexity

def complete_function_and_perplexity(informations, ground_truth_function, model, generation_config, line_number, language):
    # 确定注释符号
    if language == "python":
        comment_symbol = "# "
    else:
        comment_symbol = "// "
    
    # 创建提示信息
    if informations.endswith("\n"):
        prompt = comment_symbol + informations
    else:
        prompt = comment_symbol + informations + "\n"
    prompt += comment_symbol + "Please complete the program based on the above information\n"
    
    # 分割ground_truth_function，限制line不能超过ground_truth_function总长的一半
    function_lines = ground_truth_function.split('\n')
    total_lines = len(function_lines)

    max_lines = total_lines // 2
    if line_number > max_lines:
        line_number = max_lines

    # 生成待补全函数的前缀，由于\n符不包含任何信息，因此我们给模型line_number行确实为代码的行
    lines_count = 0
    prefix = []
    for function_line in function_lines:
        prefix.append(function_line)
        if function_line != "\n":
            lines_count += 1

        if lines_count == line_number: break
                  
    prefix = '\n'.join(prefix)
    prompt += prefix + "\n"

    # 准备消息格式
    messages = [
        # {"role": "system", "content": "You are a helpful assistant for completing code functions."},
        {"role": "user", "content": prompt}
    ]

    # 获取补全结果和概率分布
    completions, logprobs = inference(messages, generation_config, model)

    # 拼接前缀和补全结果，返回完整的函数列表
    completed_functions = [prefix + completion for completion in completions]

    # 计算困惑度
    perplexities = []
    for sequence_logprob_list in logprobs:
        perplexity = calculate_perplexity(sequence_logprob_list, len(sequence_logprob_list))
        perplexities.append(perplexity)

    assert len(completed_functions) == len(perplexities)

    return prefix, completed_functions, perplexities

# 返回int：completed_function中有多少处和ground_truth_function Type-1匹配的code snippet
def sliding_window_clone_detection(prefix, completed_function, ground_truth_function, window_size=4):
    
    match_count = 0

    completed_function = completed_function.replace(prefix, "")
    ground_truth_function = ground_truth_function.replace(prefix, "")
    
    completed_lines = completed_function.split('\n')
    ground_truth_lines = ground_truth_function.split('\n')

    completed_length = len(completed_lines)
    ground_truth_length = len(ground_truth_lines)

    # 滑动窗口检测 Type-1 克隆
    siliding_count = 0
    for i in range(min(completed_length, ground_truth_length) - window_size + 1):
        siliding_count += 1
        completed_snippet = '\n'.join(completed_lines[i:i + window_size])
        ground_truth_snippet = '\n'.join(ground_truth_lines[i:i + window_size])
        
        if completed_snippet == ground_truth_snippet:
            match_count += 1
    
    if siliding_count == 0:
        return match_count, match_count
    
    return match_count, match_count/siliding_count

# 计算bench上correct patch的平均长度
def calculate_avg_function_len(dataset_path):
  with open(dataset_path, 'r') as f:
    dataset_items = json.load(f)
  func_lens = 0
  for item in dataset_items:
      func = dataset_items[item]["buggy"]
      func = func.split("\n")
      func_lens += len(func)
  print(func_lens/len(dataset_items))

# 计算修正困惑度
def calculate_avg_perplexity(ratio_json_path):
  with open(ratio_json_path, 'r') as f:
    ratio_data = json.load(f)
  perplexities = 0
  for item in ratio_data:
    perplexity_list = ratio_data[item]["Perplexities"]
    decrease = 0
    sum_per = 0
    for perplexity in perplexity_list:
       if perplexity > math.e:
          decrease += 1
          continue
       sum_per += perplexity
    if decrease < len(perplexity_list): perplexities += sum_per / (len(perplexity_list) - decrease)
    else: perplexities += math.e
  # print(perplexities/len(ratio_data))

  return perplexities/len(ratio_data)

def calculate_avg_cnt(ratio_json_path):
  with open(ratio_json_path, 'r') as f:
    ratio_data = json.load(f)
  total_cnt = 0
  for item in ratio_data:
    cnt_list = ratio_data[item]["Type-1_count"]
    total_cnt += sum(cnt_list)
  print(len(ratio_data))
  print(len(cnt_list))
  print(total_cnt)
  print(total_cnt/len(ratio_data)/len(cnt_list))
  print()


################################################### for bugsinpy ###################################################
def generate_bugsinpy():
    
    model = "gpt-3.5-turbo-0125"
    generation_config = {
      'max_tokens': 512,
      'temperature': 0.95,
      'top_p': 0.95,
      'n': 10,
      'logprobs': 1
      # 'top_logprobs': 5
    }
    
    bench_path = "All_benchmark_info/BugsInPy_TypeBugs/bugsinpy.json"
    written_json_path = "RQ2/bugsinpy/count_ppl.json"

    with open(bench_path, 'r') as reader:
      bugsinpy_data = json.load(reader)

    all_function_count = len(bugsinpy_data)
    print("Benchmark Length: " + str(all_function_count) + "\n")

    all_json_items = {}

    # 对每一个correct patch循环
    for item in bugsinpy_data:
      project_name = item
      ground_truth_function = bugsinpy_data[item]["fix"]

      informations = f"This is the ground-truth patch function in the BugsInPy benchmark of the APR task, and its buggy version is in {project_name}"

      # window size 和 前缀长度可以算作RQ2实验的超参数
      prefix_line_num = 4
      window_size = 2
      bench_language = "python"

      # 得到n个补全后的函数，以及这n个补全函数的近似困惑度
      prefix, completed_functions, perplexities = complete_function_and_perplexity(informations, ground_truth_function, model, generation_config, prefix_line_num, bench_language)

      # 针对一个correct_patch计算count
      ground_truth_function_count = []
      # 拿滑动窗口滑动的次数修正过的count，感觉不合适衡量泄露，先记录下来
      ground_truth_function_count_rectified = []

      for i, completed_function in enumerate(completed_functions):
        # 针对一个补全函数计算Type-1匹配的计数
        single_function_type1_count, single_function_type1_count_rectified = sliding_window_clone_detection(prefix, completed_function, ground_truth_function, window_size)
        ground_truth_function_count.append(single_function_type1_count)
        ground_truth_function_count_rectified.append(single_function_type1_count_rectified)
      
      assert len(ground_truth_function_count) == len(ground_truth_function_count_rectified) == len(perplexities)
      print(project_name)
      print("Type-1 count:")
      print(ground_truth_function_count)
      print("Rectified Type-1 count")
      print(ground_truth_function_count_rectified)
      print("Perplexities:")
      print(perplexities)

      all_json_items[project_name] = {
          "Type-1_counts": ground_truth_function_count,
          "Rectified_Type-1_counts": ground_truth_function_count_rectified,
          "Perplexities": perplexities,
          "Completed_functions": completed_functions
      }

      with open(written_json_path, 'w') as f:
        json.dump(all_json_items, f, indent=2)

def calculate_bugsinpy():
  json_path = "RQ2/bugsinpy/count_ppl.json"

  with open(json_path, 'r') as f:
     json_datas = json.load(f)
  
  avg_Type1_counts = 0
  avg_Rectified_Type1_counts = 0
  avg_Perplexities = 0
  avg_Completed_functions_lines = 0

  bench_length = len(json_datas)
  print("Benchmark Length: " + str(bench_length) + "\n")
  sample_length = 10

  for item in json_datas:
    Type1_counts = json_datas[item]["Type-1_counts"]
    Rectified_Type1_counts = json_datas[item]["Rectified_Type-1_counts"]
    Perplexities = json_datas[item]["Perplexities"]
    Completed_functions = json_datas[item]["Completed_functions"]

    avg_Type1_counts += sum(Type1_counts)
    avg_Rectified_Type1_counts += sum(Rectified_Type1_counts)

    avg_Perplexities += sum(Perplexities)

    Completed_functions = [Completed_function.split("\n") for Completed_function in Completed_functions]
    avg_Completed_functions_lines += sum([len(Completed_function) for Completed_function in Completed_functions])
   
  avg_Type1_counts = avg_Type1_counts/bench_length/sample_length
  avg_Rectified_Type1_counts = avg_Rectified_Type1_counts/bench_length/sample_length
  avg_Perplexities = avg_Perplexities/bench_length/sample_length
  avg_Rectified_Perplexities = calculate_avg_perplexity(json_path)
  avg_Completed_functions_lines = avg_Completed_functions_lines/bench_length/sample_length

  print(avg_Completed_functions_lines, avg_Perplexities, avg_Rectified_Perplexities, avg_Type1_counts, avg_Rectified_Type1_counts)
################################################### for bugsinpy ###################################################


################################################### for defects4j ###################################################
def generate_d4j():

  model = "gpt-3.5-turbo-0125"
  generation_config = {
    'max_tokens': 512,
    'temperature': 0.95,
    'top_p': 0.95,
    'n': 10,
    'logprobs': 1
  }
  
  bench_path = "All_benchmark_info/Defects4J/defects4j.json"
  written_json_path = "RQ2/defects4j/sf-count_ppl.json"

  with open(bench_path, 'r') as reader:
      bugsinpy_data = json.load(reader)

  all_function_count = len(bugsinpy_data)
  print("Benchmark Length: " + str(all_function_count) + "\n")

  all_json_items = {}

  # 对每一个correct patch循环
  for item in bugsinpy_data: 
    project_name = item
    ground_truth_function = bugsinpy_data[item]["fix"]

    prefix_line_num = 4
    window_size = 2
    bench_language = "defects4j"

    if bench_language == "defects4j": # d4j
      if project_name.startswith("Chart"):
        project = "jfreechart"
      elif project_name.startswith("Cli"):
        project = "commons-cli"
      elif project_name.startswith("Closure"):
        project = "closure-compiler"
      elif project_name.startswith("Codec"):
        project = "commons-codec"
      elif project_name.startswith("Collections"):
        project = "commons-collections"
      elif project_name.startswith("Compress"):
        project = "commons-compress"
      elif project_name.startswith("Csv"):
        project = "commons-csv"
      elif project_name.startswith("Gson"):
        project = "commons-compress"
      elif project_name.startswith("gson"):
        project = "commons-compress"
      elif project_name.startswith("JacksonCore"):
        project = "jackson-core"
      elif project_name.startswith("JacksonDatabind"):
        project = "jackson-databind"
      elif project_name.startswith("JacksonXml"):
        project = "jackson-dataformat-xml"
      elif project_name.startswith("Jsoup"):
        project = "jsoup"
      elif project_name.startswith("JxPath"):
        project = "commons-jxpath"
      elif project_name.startswith("Lang"):
        project = "commons-lang"
      elif project_name.startswith("Math"):
        project = "commons-math"
      elif project_name.startswith("Mockito"):
        project = "mockito"
      else:
          project = "joda-time"
      name_0 = project_name.split("-")[0]
      name_1 = project_name.split("-")[1]
      try:
        with open(os.path.join("main-Defects4J/framework/projects", name_0, "modified_classes", name_1+".src"), 'r') as reader:
          modified_classes = reader.read().replace("\n", "")
        informations = f"This is the ground-truth patch function in the Defects4J benchmark of the APR task, its buggy version is in {project} {project_name}, and its modified class is {modified_classes}" 
      except Exception as e:
        informations = f"This is the ground-truth patch function in the Defects4J benchmark of the APR task, its buggy version is in {project} {project_name}"
    else:
      informations = f"This is the ground-truth patch function in the Defects4J benchmark of the APR task, its buggy version is in {project_name}"

    prefix, completed_functions, perplexities = complete_function_and_perplexity(informations, ground_truth_function, model, generation_config, prefix_line_num, bench_language)

    print(project_name)
    print("Perplexities:")
    print(perplexities)

    # 记入dict
    all_json_items[project_name] = {
      "Prefix": prefix,
      "Perplexities": perplexities,
      "Completed_functions": completed_functions
    }

    # 每一个correct patch写入一次，以防没跑完整个bench数据丢失
    with open(written_json_path, 'w') as f:
      json.dump(all_json_items, f, indent=2)

def calculate_d4j_all():
  json_path = "RQ2/defects4j/sf-count_ppl.json"
  bench_path = "All_benchmark_info/Defects4J/defects4j.json"
  written_json_path = "RQ2/defects4j/sf-count_ppl_plus.json"
  all_json_items={}

  with open(json_path, 'r') as f:
     json_datas = json.load(f)
  
  with open(bench_path, 'r') as f:
     bench_datas = json.load(f) 
  
  avg_Type1_counts = 0
  avg_Rectified_Type1_counts = 0
  avg_Perplexities = 0
  avg_Completed_functions_lines = 0

  bench_length = len(json_datas)
  print("Benchmark Length: " + str(bench_length) + "\n")
  sample_length = 10

  for item in json_datas:
    prefix = json_datas[item]["Prefix"]
    perplexities = json_datas[item]["Perplexities"]
    completed_functions = json_datas[item]["Completed_functions"]

    correct_patch = bench_datas[item]["fix"]


    match_count_list=[]
    rectified_match_count_list = []
    for completed_function in completed_functions:
       
      completed_function = completed_function.replace(prefix, "")
      correct_patch = correct_patch.replace(prefix, "")

      completed_function = completed_function.split("\n")
      correct_patch = correct_patch.split("\n")

      completed_function = [item for item in completed_function if item != ""]
      correct_patch = [item for item in correct_patch if item != ""]

      completed_function = prefix + "\n".join(completed_function)
      correct_patch = prefix + "\n".join(correct_patch)

      match_count, rectified_match_count = sliding_window_clone_detection(prefix, completed_function, correct_patch, window_size=2)

      match_count_list.append(match_count)
      rectified_match_count_list.append(rectified_match_count)

    avg_Type1_counts += sum(match_count_list)
    avg_Rectified_Type1_counts += sum(rectified_match_count_list)

    avg_Perplexities += sum(perplexities)

    Completed_functions = [completed_function.split("\n") for completed_function in completed_functions]
    avg_Completed_functions_lines += sum([len(Completed_function) for Completed_function in Completed_functions])

    # 记入dict
    all_json_items[item] = {
        "Type-1_counts": match_count_list,
        "Rectified_Type-1_counts": rectified_match_count_list,
        "Perplexities": perplexities,
        "Completed_functions": completed_functions
    }
    # 写入新的json
    with open(written_json_path, 'w') as f:
      json.dump(all_json_items, f, indent=2)

  avg_Type1_counts = avg_Type1_counts/bench_length/sample_length
  avg_Rectified_Type1_counts = avg_Rectified_Type1_counts/bench_length/sample_length
  avg_Perplexities = avg_Perplexities/bench_length/sample_length
  avg_Rectified_Perplexities = calculate_avg_perplexity(json_path)
  avg_Completed_functions_lines = avg_Completed_functions_lines/bench_length/sample_length

  print(avg_Completed_functions_lines, avg_Perplexities, avg_Rectified_Perplexities, avg_Type1_counts, avg_Rectified_Type1_counts)
################################################### for defects4j ###################################################


################################################### for typebugs ###################################################
def generate_typebugs():
  model = "gpt-3.5-turbo-0125"
  generation_config = {
    'max_tokens': 512,
    'temperature': 0.95,
    'top_p': 0.95,
    'n': 10,
    'logprobs': 1
  }
  
  bench_path = "All_benchmark_info/BugsInPy_TypeBugs/typebugs.json"
  written_json_path = "RQ2/typebugs/count_ppl.json"

  with open(bench_path, 'r') as reader:
      bugsinpy_data = json.load(reader)

  all_function_count = len(bugsinpy_data)
  print("Benchmark Length: " + str(all_function_count) + "\n")

  all_json_items = {}

  # 对每一个correct patch循环
  for item in bugsinpy_data: 
    project_name = item
    ground_truth_function = bugsinpy_data[item]["fix"]

    prefix_line_num = 4
    window_size = 2
    bench_language = "python"

    informations = f"This is the ground-truth patch function in the TypeBugs benchmark of the APR task, its buggy version is in {project_name}"

    prefix, completed_functions, perplexities = complete_function_and_perplexity(informations, ground_truth_function, model, generation_config, prefix_line_num, bench_language)

    print(project_name)
    print("Perplexities:")
    print(perplexities)

    # 记入dict
    all_json_items[project_name] = {
      "Prefix": prefix,
      "Perplexities": perplexities,
      "Completed_functions": completed_functions
    }

    # 每一个correct patch写入一次，以防没跑完整个bench数据丢失
    with open(written_json_path, 'w') as f:
      json.dump(all_json_items, f, indent=2)

def calculate_typebugs_all():
  json_path = "RQ2/typebugs/count_ppl.json"
  bench_path = "All_benchmark_info/BugsInPy_TypeBugs/typebugs_109.json"
  written_json_path = "RQ2/typebugs/count_ppl_plus.json"
  all_json_items={}

  with open(json_path, 'r') as f:
     json_datas = json.load(f)
  
  with open(bench_path, 'r') as f:
     bench_datas = json.load(f) 
  
  avg_Type1_counts = 0
  avg_Rectified_Type1_counts = 0
  avg_Perplexities = 0
  avg_Completed_functions_lines = 0

  bench_length = len(json_datas)
  print("Benchmark Length: " + str(bench_length) + "\n")
  sample_length = 10

  for item in json_datas:
    prefix = json_datas[item]["Prefix"]
    perplexities = json_datas[item]["Perplexities"]
    completed_functions = json_datas[item]["Completed_functions"]

    correct_patch = bench_datas[item]["fix"]


    match_count_list=[]
    rectified_match_count_list = []
    for completed_function in completed_functions:
       
      completed_function = completed_function.replace(prefix, "")
      correct_patch = correct_patch.replace(prefix, "")

      completed_function = completed_function.split("\n")
      correct_patch = correct_patch.split("\n")

      completed_function = [item for item in completed_function if item != ""]
      correct_patch = [item for item in correct_patch if item != ""]

      completed_function = prefix + "\n".join(completed_function)
      correct_patch = prefix + "\n".join(correct_patch)

      match_count, rectified_match_count = sliding_window_clone_detection(prefix, completed_function, correct_patch, window_size=2)

      match_count_list.append(match_count)
      rectified_match_count_list.append(rectified_match_count)

    avg_Type1_counts += sum(match_count_list)
    avg_Rectified_Type1_counts += sum(rectified_match_count_list)

    avg_Perplexities += sum(perplexities)

    Completed_functions = [completed_function.split("\n") for completed_function in completed_functions]
    avg_Completed_functions_lines += sum([len(Completed_function) for Completed_function in Completed_functions])

    # 记入dict
    all_json_items[item] = {
        "Type-1_counts": match_count_list,
        "Rectified_Type-1_counts": rectified_match_count_list,
        "Perplexities": perplexities,
        "Completed_functions": completed_functions
    }
    # 写入新的json
    with open(written_json_path, 'w') as f:
      json.dump(all_json_items, f, indent=2)

  avg_Type1_counts = avg_Type1_counts/bench_length/sample_length
  avg_Rectified_Type1_counts = avg_Rectified_Type1_counts/bench_length/sample_length
  avg_Perplexities = avg_Perplexities/bench_length/sample_length
  avg_Rectified_Perplexities = calculate_avg_perplexity(json_path)
  avg_Completed_functions_lines = avg_Completed_functions_lines/bench_length/sample_length

  print(avg_Completed_functions_lines, avg_Perplexities, avg_Rectified_Perplexities, avg_Type1_counts, avg_Rectified_Type1_counts)
################################################### for typebugs ###################################################


################################################### for humaneval-java ###################################################
def calculate_avg_humanevaljava_len(dataset_path):
  avg_len = 0
  for file_name in os.listdir(dataset_path):
    with open(os.path.join(dataset_path, file_name), 'r') as correct_patch_file:
      correct_patch = correct_patch_file.readlines()
    correct_patch = remove_empty_line(remove_comment("\n".join(correct_patch)))
    # correct_patch = "\n".join(correct_patch)
    correct_patch = correct_patch.split("\n")
    
    avg_len += len(correct_patch)
    
  avg_len = avg_len / len(os.listdir(dataset_path))
  
  print(avg_len)
      
def generate_humanevaljava():
  model = "gpt-3.5-turbo-0125"
  generation_config = {
    'max_tokens': 512,
    'temperature': 0.95,
    'top_p': 0.95,
    'n': 10,
    'logprobs': 1
    # 'top_logprobs': 5
  }
  
  bench_path = "main-HumanEval-java/src/main/java/humaneval/correct"
  written_json_path = "RQ2_results/humanevaljava/count_ppl.json"
  
  bench_len = len(os.listdir(bench_path))
  print("Benchmark Length: " + str(bench_len) + "\n")

  all_json_items = {}

  # 对每一个correct patch循环
  for file_name in os.listdir(bench_path):
    
    correct_patch = open(os.path.join(bench_path, file_name), 'r').readlines()
    correct_patch = remove_empty_line(remove_comment("\n".join(correct_patch)))
    open(os.path.join(bench_path, file_name), 'r').close()
    
    # informations
    info = f"This is the correct patch in the HumanEval-Java benchmark for the APR task, and its buggy version is in {file_name}. HumanEval-Java includes buggy and correct Java programs transformed from HumanEval dataset."
    
    # win size and prefix len
    prefix_len = 4
    win_size = 2
    bench_language = "java"

    # 对一个correct patch得到10个补全函数，以及这10个函数的困惑度
    prefix, completed_func_list, ppl_list = complete_function_and_perplexity(info, correct_patch, model, generation_config, prefix_len, bench_language)
    
    # 针对一个correct patch计算count
    completed_func_count = []
    rectified_completed_func_count = []
    
    for i, completed_func in enumerate(completed_func_list):
      # 针对一个补全函数计算Type-1匹配的计数
      single_function_type1_count, single_function_type1_count_rectified = sliding_window_clone_detection(prefix, completed_func, correct_patch, win_size)
      completed_func_count.append(single_function_type1_count)
      rectified_completed_func_count.append(single_function_type1_count_rectified)
    
    assert len(completed_func_count) == len(rectified_completed_func_count) == len(ppl_list) == 10
    print(file_name)
    print("Type-1 count:")
    print(completed_func_count)
    print("Rectified Type-1 count")
    print(rectified_completed_func_count)
    print("Perplexities:")
    print(ppl_list)
    
    # 记入dict
    all_json_items[file_name] = {
      "Type-1_counts": completed_func_count,
      "Rectified_Type-1_counts": rectified_completed_func_count,
      "Perplexities": ppl_list,
      "Completed_functions": completed_func_list
    }

    # 每一个correct patch写入一次，以防没跑完整个bench数据丢失
    with open(written_json_path, 'w') as f:
      json.dump(all_json_items, f, indent=2)

def calculate_humanevaljava():
  json_path = "RQ2_results/humanevaljava/count_ppl.json"
  bench_path = "main-HumanEval-java/src/main/java/humaneval/correct"
  # written_json_path = "RQ2_results/humanevaljava/count_ppl_plus.json"
  # all_json_items={}
  
  with open(json_path, 'r') as f:
     json_datas = json.load(f) 
  
  avg_Type1_counts = 0
  avg_Rectified_Type1_counts = 0
  avg_Perplexities = 0
  avg_Completed_functions_lines = 0
  
  bench_len = len(json_datas)
  print("Benchmark Length: " + str(bench_len) + "\n")
  sample_length = 10
  
  for file_name in os.listdir(bench_path):
    type_1_counts = json_datas[file_name]["Type-1_counts"]
    re_Type_1_counts = json_datas[file_name]["Rectified_Type-1_counts"]
    
    perplexities = json_datas[file_name]["Perplexities"]
    completed_functions = json_datas[file_name]["Completed_functions"]
    
    avg_Type1_counts += sum(type_1_counts)
    avg_Rectified_Type1_counts += sum(re_Type_1_counts)
    
    avg_Perplexities += sum(perplexities)
    avg_Completed_functions_lines += sum([len(completed_function.split("\n")) for completed_function in completed_functions])
    
    
  avg_Type1_counts = avg_Type1_counts/bench_len/sample_length
  avg_Rectified_Type1_counts = avg_Rectified_Type1_counts/bench_len/sample_length
  avg_Perplexities = avg_Perplexities/bench_len/sample_length
  avg_Rectified_Perplexities = calculate_avg_perplexity(json_path)
  avg_Completed_functions_lines = avg_Completed_functions_lines/bench_len/sample_length

  print(avg_Completed_functions_lines, avg_Perplexities, avg_Rectified_Perplexities, avg_Type1_counts, avg_Rectified_Type1_counts)

def humaneval_complete_function_and_perplexity(informations, humaneval_prefix, model, generation_config, language):
    # 确定注释符号
    if language == "python":
        comment_symbol = "# "
    else:
        comment_symbol = "// "
    
    # 创建提示信息
    if informations.endswith("\n"):
        prompt = comment_symbol + informations
    else:
        prompt = comment_symbol + informations + "\n"
        
    prompt += comment_symbol + "Please complete the program based on the above information\n"
    prompt += humaneval_prefix + "\n"

    # 准备消息格式
    messages = [
        # {"role": "system", "content": "You are a helpful assistant for completing code functions."},
        {"role": "user", "content": prompt}
    ]

    # 获取补全结果和概率分布
    completions, logprobs = inference(messages, generation_config, model)

    # 拼接前缀和补全结果，返回完整的函数列表
    completed_functions = completions

    # 计算困惑度
    perplexities = []
    for sequence_logprob_list in logprobs:
        perplexity = calculate_perplexity(sequence_logprob_list, len(sequence_logprob_list))
        perplexities.append(perplexity)

    assert len(completed_functions) == len(perplexities)

    return  completed_functions, perplexities

def humaneval_sliding_window_clone_detection(completed_function, ground_truth_function, window_size):
    match_count = 0
    
    completed_lines = completed_function.split('\n')
    ground_truth_lines = ground_truth_function.split('\n')

    completed_length = len(completed_lines)
    ground_truth_length = len(ground_truth_lines)

    # 滑动窗口检测 Type-1 克隆
    siliding_count = 0
    for i in range(min(completed_length, ground_truth_length) - window_size + 1):
        siliding_count += 1
        completed_snippet = '\n'.join(completed_lines[i:i + window_size])
        ground_truth_snippet = '\n'.join(ground_truth_lines[i:i + window_size])
        
        if completed_snippet == ground_truth_snippet:
            match_count += 1
    
    if siliding_count == 0:
        return match_count, match_count
    
    return match_count, match_count/siliding_count
 
def generate_humaneval():
  model = "gpt-3.5-turbo-0125"
  generation_config = {
    'max_tokens': 512,
    'temperature': 0.95,
    'top_p': 0.95,
    'n': 10,
    'logprobs': 1
  }
  
  bench_path = "main-HumanEval/data/human-eval.jsonl"
  written_json_path = "RQ_2_results/humaneval/count_ppl.json"
  
  with open(bench_path) as reader:
    json_filedata = reader.readlines()
    
  import ast
  bench_datas = []
  for strdata in json_filedata:
    test_dict = ast.literal_eval(strdata)
    bench_datas.append(test_dict)
  print("Benchmark Length: " + str(len(bench_datas)) + "\n")
  
  all_json_items = {}

  test = 0
  # 对每一个humaneval i循环
  for data in bench_datas:
    # if test == 1: break ###################################################################################### for test
    test += 1
    file_name = data["task_id"]
    canonical_solution_head = data["prompt"]
    
    # informations
    info = f"This is a canonical solution head in the HumanEval benchmark that is a very famous benchmark for Code Generation and Completion tasks, and its file name is {file_name}."
    
    # win size and prefix len
    prefix_len = 4
    win_size = 2
    bench_language = "python"

    # 对一个correct patch得到10个补全函数，以及这10个函数的困惑度
    completed_func_list, ppl_list = humaneval_complete_function_and_perplexity(info, canonical_solution_head, model, generation_config, bench_language)
    
    
    assert len(completed_func_list) == len(ppl_list) == 10
    print(file_name)
    print("Perplexities:")
    print(ppl_list)
    
    # 记入dict
    all_json_items[file_name] = {
      "Prefix": canonical_solution_head,
      "Perplexities": ppl_list,
      "Completed_functions": completed_func_list
    }

    # 每一个correct patch写入一次，以防没跑完整个bench数据丢失
    with open(written_json_path, 'w') as f:
      json.dump(all_json_items, f, indent=2)

def calculate_humaneval():
  json_path = "RQ_2_results/humaneval/count_ppl.json"
  bench_path = "main-HumanEval/data/human-eval.jsonl"
  written_json_path = "RQ_2_results/humaneval/count_ppl_plus.json"
  all_json_items={}

  with open(json_path, 'r') as f:
     json_datas = json.load(f)
  
  with open(bench_path) as reader:
    json_filedata = reader.readlines()
    
  import ast
  bench_datas = []
  for strdata in json_filedata:
    test_dict = ast.literal_eval(strdata)
    bench_datas.append(test_dict)
  print("Benchmark Length: " + str(len(bench_datas)) + "\n")
  
  bench_length = len(bench_datas)
  sample_length = 10
  
  avg_Type1_counts = 0
  avg_Rectified_Type1_counts = 0
  avg_Perplexities = 0
  avg_Completed_functions_lines = 0

  for i, item in enumerate(json_datas):
    prefix = json_datas[item]["Prefix"]
    perplexities = json_datas[item]["Perplexities"]
    completed_functions = json_datas[item]["Completed_functions"]

    correct_patch = bench_datas[i]["canonical_solution"]


    match_count_list=[]
    rectified_match_count_list = []
    for completed_function in completed_functions:
      match_count, rectified_match_count = humaneval_sliding_window_clone_detection(completed_function, correct_patch, window_size=2)

      match_count_list.append(match_count)
      rectified_match_count_list.append(rectified_match_count)

    avg_Type1_counts += sum(match_count_list)
    avg_Rectified_Type1_counts += sum(rectified_match_count_list)

    avg_Perplexities += sum(perplexities)

    Completed_functions = [completed_function.split("\n") for completed_function in completed_functions]
    avg_Completed_functions_lines += sum([len(Completed_function) for Completed_function in Completed_functions])
    
    # 记入dict
    all_json_items[item] = {
        "Type-1_counts": match_count_list,
        "Rectified_Type-1_counts": rectified_match_count_list,
        "Perplexities": perplexities,
        "Completed_functions": completed_functions
    }
    # 写入新的json
    with open(written_json_path, 'w') as f:
      json.dump(all_json_items, f, indent=2)

  avg_Type1_counts = avg_Type1_counts/bench_length/sample_length
  avg_Rectified_Type1_counts = avg_Rectified_Type1_counts/bench_length/sample_length
  avg_Perplexities = avg_Perplexities/bench_length/sample_length
  avg_Rectified_Perplexities = calculate_avg_perplexity(json_path)
  avg_Completed_functions_lines = avg_Completed_functions_lines/bench_length/sample_length

  print(avg_Completed_functions_lines, avg_Perplexities, avg_Rectified_Perplexities, avg_Type1_counts, avg_Rectified_Type1_counts)
################################################### for humaneval-java ###################################################

  
if __name__ == '__main__':
  
  calculate_humaneval()