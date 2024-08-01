
def get_first_fix(lang, code):
    msgs = [{
        'role' : "system",
        'content' : 'You are an expert in software, please fix the following code.'
    }]
    next_msg = [
        {
            'role': 'user',
            'content': "".join([f'You sould analyze and fix the code step by step, ensure the fixed {lang} function code is buggy-free. Only to answer the fixed code function, No more any other output!!\n', 
                                f'The fault codes followed as:\n{code}'])
        }
    ]
    return msgs + next_msg


def check_if_bug(lang, code):
    msgs = [
        {
            'role' : "system",
            'content' : 'You are an expert in software fix, please vertify if the following code if buggy.'
        }
    ]
    
    next_msg = [
        {
            'role': 'user',
            'content': ''.join([f'Please vertify the {lang} function to think if the code is buggy or correct. You should only answer yes or no, no more any other output.',
                    f'Code:\n{code}'])
        }
    ]
    return msgs + next_msg

def generate_trp(lang, fixed_code):
    msgs = [
        {
            'role': 'system', 
            'content': f'You are an expert in software test, please vertify the {lang} code and generate test report based on function code.'
        }, 
        {
            'role': 'user', 
            'content': f'Code:\n{fixed_code}'
        }
    ]
    
    return msgs

def fix_baed_on_report(lang, report, code):
    msgs = [
        	{
            'role': 'system', 
            'content': f'You are an expert in software fix, fix the {lang} code and ensure that the fixed code is bug-free according to test report.'
            }, 
            {
                'role': 'user', 
                'content': f'You should analyze and fix the code step by step based on test report offered and fix the code.\nYou shoul only answer the fixed function code. No more any other output.\nTest report:{report}\nCode:\n{code}'
            }
    ]