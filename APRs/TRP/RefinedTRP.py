import logging
import openai
from retry import retry
import os
import sys
sys.path.append(os.getcwd())
import json
import argparse
from trp_consists import *

parser = argparse.ArgumentParser(description='Repair based on TRP')
parser.add_argument('-out', type=str, help='output json path')
parser.add_argument('-code', type=str, help='code json path')
parser.add_argument('-api', type=str)
parser.add_argument('-model', default="gpt-3.5-turbo-0125", type=str)
parser.add_argument('-lang', default='Python', type=str)

args = parser.parse_args()
api_key = args.api
out_path = args.out
lang = args.lang
to_be_fixed = {}
be_fixed_path = args.code
with open(be_fixed_path, 'r') as f:
    to_be_fixed = json.load(f)
model_name = args.model
client = openai.OpenAI(
                api_key = api_key
                # base_url ='https://api.chatanywhere.tech/v1'
            )
token_limit = 4000
temperture = 0
top_p = 1

@retry((openai.APIConnectionError, openai.APIError, openai.Timeout), delay=2, backoff=2)
def launch_chatgpt(msgs):
    try:
        response = client.chat.completions.create(
            model=model_name, 
            messages=msgs,
            temperature=temperture,
            top_p=top_p
        )
    except:
        logging.warning("openai.BadRequestError: Error code: 400 - {'detail': 'Content Exists Risk'}")
        return None
    status_code = response.choices[0].finish_reason
    if status_code == "stop":
        return response.choices[0].message.content
    elif status_code == "length":
        logging.warning(f"The response is too long {len(response.choices[0].message.content)}")
        return response.choices[0].message.content
    elif status_code == "content_filter":
        logging.warning("Input contains risky contents!")
        return None
    else:
        logging.warning(response.choices[0].message.content)
        raise ValueError(f"The status code was {status_code}.")
    
    
if __name__ == '__main__':
    res_dict = {}
    for key in to_be_fixed.keys():
        code = to_be_fixed[key]["buggy"]
        msg = get_first_fix(lang, code)
        code_fixed_round1 = launch_chatgpt(msg)
        res_dict[key]['patches'] = [code_fixed_round1]
        msg = check_if_bug(lang, code_fixed_round1)
        if_buggy = launch_chatgpt(msg)
        if msg == 'no':
            continue
        test_report_msg = generate_trp(lang, code_fixed_round1)
        test_report = launch_chatgpt(test_report_msg)
        code_fixed_round2 = launch_chatgpt(fix_baed_on_report(lang, test_report, code_fixed_round1))
        res_dict[key]['patches'].append(code_fixed_round2)
    with open(out_path, 'w') as f:
        json.dump(res_dict, f, indent=4)
        