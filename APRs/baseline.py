from openai import OpenAI


def get_bugsinpy_typebugs_base_prompt(buggy_function, buggy_lines, prefix):
  b_empty = False
  if buggy_lines == "":
      buggy_lines = "blank, so some code is missing after the buggy prefix causing the bug. The buggy prefix is: " + prefix
      b_empty = True

  if not b_empty:
    messages1 = {"role": "user", "content": "You are a professional Python programmer helping me with repairing a bug. The buggy function is: {}\nThe buggy line is: {}\nPlease fix the buggy line step by step. Attention you can only fix the buggy line and are forbidden to change other lines, add new lines, delete certain lines, or generate any natural language, and I'm pretty sure that fixing only the buggy line will make the buggy function correct. Please give me the complete fixed function in the following format: #fixed funtion: (your response).".format(buggy_function, buggy_lines)
      }
  else:
      messages1 = {"role": "user", "content": "You are a professional Python programmer helping me with repairing a bug. The buggy function is: {}\nThe buggy line is {}\nPlease generate some code after the buggy prefix as the fixed line, and give me the complete fixed function in the following format: #fixed line: (your response). ".format(buggy_function, buggy_lines)
      }
  return messages1

def get_humanevaljava_base_prompt(buggy_function, buggy_loc):
  
  prompt = f"You are a professional Java programmer helping me with repairing a bug. The buggy class is:\n{buggy_function}\nThe line number of the buggy lines is: {buggy_loc}\nPlease fix the buggy line step by step. Attention you can only fix the buggy line and are forbidden to change other lines, add new lines, delete certain lines, or generate any natural language, and I'm pretty sure that fixing only the buggy line will make the buggy class correct. Please give me the complete fixed class in the following format: //fixed class: (your response)."
  
  messages = {"role": "user", "content": prompt}
  
  return messages

def get_d4j_base_prompt(buggy_function, fixed_function, start, end):
  
  line_gap = int(end) - int(start)
  buggy_line_start = 0
  
  buggy_function_list = buggy_function.split("\n")
  fixed_function_list = fixed_function.split("\n")
  
  for i in range(min(len(buggy_function_list), len(fixed_function_list))):
    if buggy_function_list[i] != fixed_function_list[i]:
      buggy_line_start = i+1
      break
  
  if buggy_line_start:
    buggy_line_end = buggy_line_start + line_gap
    prompt = f"You are a professional Java programmer helping me with repairing a bug. The buggy function is:\n{buggy_function}\nThe line number of the buggy lines is: {str(buggy_line_start)}-{str(buggy_line_end)}\nPlease fix the buggy line step by step. Attention you can only fix the buggy line and are forbidden to change other lines, add new lines, delete certain lines, or generate any natural language, and I'm pretty sure that fixing only the buggy line will make the buggy function correct. Please give me the complete fixed function in the following format: //fixed funtion: (your response)."
  else:
    prompt = f"You are a professional Java programmer helping me with repairing a bug. The buggy function is:\n{buggy_function}\nPlease fix the buggy line step by step. Attention you can only fix the buggy line and are forbidden to change other lines, add new lines, delete certain lines, or generate any natural language, and I'm pretty sure that fixing only the buggy line will make the buggy function correct. Please give me the complete fixed function in the following format: //fixed funtion: (your response)."
  
  messages = {"role": "user", "content": prompt}
  
  return messages


fee_client = OpenAI(
    api_key="yours",
    # base_url="https://api.chatanywhere.tech/v1"
)

def api_gpt3_5_response_fee(messages, n):
  response = fee_client.chat.completions.create(    
      messages=[messages],
      model="gpt-3.5-turbo-0125",
      n=n,
      temperature=0.95,
      top_p=0.95
      )
  return response



if __name__ == "__main__":
  # repair
  pass

