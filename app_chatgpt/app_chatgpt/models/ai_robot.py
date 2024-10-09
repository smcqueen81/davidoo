# -*- coding: utf-8 -*-

import os
from openai import OpenAI
from openai import AzureOpenAI
import requests, json
import base64

from odoo import api, fields, models, modules, tools, _
from odoo.exceptions import UserError

import logging
_logger = logging.getLogger(__name__)


class AiRobot(models.Model):
    _name = 'ai.robot'
    _description = 'Ai Robot'
    _order = 'sequence, name'

    name = fields.Char(string='Name', translate=True, required=True)
    provider = fields.Selection(string="AI Provider", selection=[('openai', 'OpenAI'), ('azure', 'Azure')],
                                required=True, default='openai', change_default=True)
    # update ai_robot set ai_model=set_ai_model
    ai_model = fields.Char(string="Ai Model", required=True, default='auto', help='Customize input')
    set_ai_model = fields.Selection(string="Quick Set Model", selection=[
        ('gpt-3.5-turbo-0125', 'gpt-3.5-turbo-0125(Default and Latest)'),
        ('gpt-3.5-turbo-0613', 'gpt-3.5-turbo-0613'),
        ('gpt-3.5-turbo-0125', 'gpt-3.5-turbo-0125'),
        ('gpt-3.5-turbo-16k-0613', 'gpt-3.5-turbo-16k-0613(Big text)'),
        ('gpt-4o', 'GPT-4o'),
        ('gpt-4-turbo', 'GPT-4 Turbo'),
        ('gpt-4', 'Chatgpt 4'),
        ('gpt-4-32k', 'Chatgpt 4 32k'),
        ('gpt-3.5-turbo', 'Chatgpt 3.5 Turbo'),
        ('gpt-3.5-turbo-0301', 'Chatgpt 3.5 Turbo on 20230301'),
        ('text-davinci-003', 'Chatgpt 3 Davinci'),
        ('code-davinci-002', 'Chatgpt 2 Code Optimized'),
        ('text-davinci-002', 'Chatgpt 2 Davinci'),
        ('dall-e2', 'Dall-E Image'),
    ], default='gpt-3.5-turbo-0125',
                                help="""
GPT-4: Can understand Image, generate natural language or code.
GPT-3.5: A set of models that improve on GPT-3 and can understand as well as generate natural language or code
DALL·E: A model that can generate and edit images given a natural language prompt
Whisper: A model that can convert audio into text
Embeddings:	A set of models that can convert text into a numerical form
CodexLimited: A set of models that can understand and generate code, including translating natural language to code
Moderation: A fine-tuned model that can detect whether text may be sensitive or unsafe
GPT-3	A set of models that can understand and generate natural language
                             """)
    openapi_api_key = fields.Char(string="API Key", help="Provide the API key here")
    # begin gpt 参数
    # 1. stop：表示聊天机器人停止生成回复的条件，可以是一段文本或者一个列表，当聊天机器人生成的回复中包含了这个条件，就会停止继续生成回复。
    # 2. temperature：0-2，控制回复的“新颖度”，值越高，聊天机器人生成的回复越不确定和随机，值越低，聊天机器人生成的回复会更加可预测和常规化。
    # 3. top_p：0-1，语言连贯性，与temperature有些类似，也是控制回复的“新颖度”。不同的是，top_p控制的是回复中概率最高的几个可能性的累计概率之和，值越小，生成的回复越保守，值越大，生成的回复越新颖。
    # 4. frequency_penalty：-2~2，用于控制聊天机器人回复中出现频率过高的词汇的惩罚程度。聊天机器人会尝试避免在回复中使用频率较高的词汇，以提高回复的多样性和新颖度。
    # 5. presence_penalty：-2~2与frequency_penalty相对，用于控制聊天机器人回复中出现频率较低的词汇的惩罚程度。聊天机器人会尝试在回复中使用频率较低的词汇，以提高回复的多样性和新颖度。
    max_tokens = fields.Integer('Max Response', default=600,
                                help="""
                                Set a limit on the number of tokens per model response.
                                The API supports a maximum of 4000 tokens shared between the prompt
                                (including system message, examples, message history, and user query) and the model's response.
                                One token is roughly 4 characters for typical English text.
                                """)
    temperature = fields.Float(string='Temperature', default=1,
                               help="""
                               Controls randomness. Lowering the temperature means that the model will produce
                               more repetitive and deterministic responses.
                               Increasing the temperature will result in more unexpected or creative responses.
                               Try adjusting temperature or Top P but not both.
                                    """)
    top_p = fields.Float('Top Probabilities', default=0.6,
                         help="""
                         Similar to temperature, this controls randomness but uses a different method.
                         Lowering Top P will narrow the model’s token selection to likelier tokens.
                         Increasing Top P will let the model choose from tokens with both high and low likelihood.
                         Try adjusting temperature or Top P but not both
                         """)
    # 避免使用常用词
    frequency_penalty = fields.Float('Frequency Penalty', default=1,
                                     help="""
                                     Reduce the chance of repeating a token proportionally based on how often it has appeared in the text so far.
                                     This decreases the likelihood of repeating the exact same text in a response.
                                     """)
    # 越大模型就趋向于生成更新的话题，惩罚已经出现过的文本
    presence_penalty = fields.Float('Presence penalty', default=1,
                                    help="""
                                    Reduce the chance of repeating any token that has appeared in the text at all so far.
                                    This increases the likelihood of introducing new topics in a response.
                                    """)
    # 停止回复的关键词
    stop = fields.Char('Stop sequences',
                       help="""
                       Use , to separate the stop key word.
                       Make responses stop at a desired point, such as the end of a sentence or list.
                       Specify up to four sequences where the model will stop generating further tokens in a response.
                       The returned text will not contain the stop sequence.
                       """)
    # 角色设定
    sys_content = fields.Char('System message',
                              help="""
                              Give the model instructions about how it should behave and any context it should reference when generating a response.
                              You can describe the assistant’s personality,
                              tell it what it should and shouldn’t answer, and tell it how to format responses.
                              There’s no token limit for this section, but it will be included with every API call,
                              so it counts against the overall token limit.
                              """)
    # end gpt 参数
    endpoint = fields.Char('End Point', default='https://api.openai.com/v1/chat/completions')
    engine = fields.Char('Engine', help='If use Azure, Please input the Model deployment name.')
    api_version = fields.Char('API Version', default='2022-12-01')
    ai_timeout = fields.Integer('Timeout(seconds)', help="Connect timeout for Ai response", default=120)
    sequence = fields.Integer('Sequence', help="Determine the display order", default=10)
    sensitive_words = fields.Text('Sensitive Words Plus', help='Sensitive word filtering. Separate keywords with a carriage return.')
    is_filtering = fields.Boolean('Filter Sensitive Words', default=False, help='Use base Filter in dir models/lib/sensi_words.txt')

    max_send_char = fields.Integer('Max Send Char', help='Max Send Prompt Length', default=8000)
    image_avatar = fields.Image('Avatar')
    partner_ids = fields.One2many('res.partner', 'gpt_id', string='Partner')
    partner_count = fields.Integer('#Partner', compute='_compute_partner_count', store=False)
    active = fields.Boolean('Active', default=True)

    def _compute_partner_count(self):
        for rec in self:
            rec.partner_count = len(rec.partner_ids)

    def action_disconnect(self):
        requests.delete('https://chatgpt.com/v1/disconnect')

    def get_ai_pre(self, data, author_id=False, answer_id=False, param={}):
        # hook，都正常
        return False

    def get_ai(self, data, author_id=False, answer_id=False, param={}):
        #     通用方法
        # author_id: 请求的 partner_id 对象
        # answer_id: 回答的 partner_id 对象
        # param，dict 形式的参数
        # 调整输出为2个参数：res_post详细内容，is_ai是否ai的响应
        
        self.ensure_one()
        # 前置勾子，一般返回 False，有问题返回响应内容，用于处理敏感词等
        res_pre = self.get_ai_pre(data, author_id, answer_id, param)
        if res_pre:
            # 有错误内容，则返回上级内容及 is_ai为假
            return res_pre, {}, False
        if not hasattr(self, 'get_%s' % self.provider):
            res = _('No robot provider found')
            return res, {}, False
        
        res = getattr(self, 'get_%s' % self.provider)(data, author_id, answer_id, param)
        # 后置勾子，返回处理后的内容
        res_post, usage, is_ai = self.get_ai_post(res, author_id, answer_id,  param)
        return res_post, usage, is_ai

    def get_ai_origin(self, data, author_id=False, answer_id=False, param={}):
        # 通用方法
        # author_id: 请求的 partner_id 对象
        # answer_id: 回答的 partner_id 对象
        # param，dict 形式的参数
        # 调整输出为2个参数：res_post详细内容，is_ai是否ai的响应

        self.ensure_one()
        # 前置勾子，一般返回 False，有问题返回响应内容，用于处理敏感词等
        res_pre = self.get_ai_pre(data, author_id, answer_id, param)
        if res_pre:
            # 有错误内容，则返回上级内容及 is_ai为假
            return res_pre, {}, False
        if not hasattr(self, 'get_%s' % self.provider):
            res = _('No robot provider found')
            return res, {}, False

        res = getattr(self, 'get_%s' % self.provider)(data, author_id, answer_id, param)
        # 后置勾子，返回处理后的内容
        res_post, usage, is_ai = self.get_ai_post(res, author_id, answer_id, param)
        return res
    
    def get_ai_post(self, res, author_id=False, answer_id=False, param=None):
        # hook，高级版要替代
        if param is None:
            param = {}
        if not res or not author_id or (not isinstance(res, list) and not isinstance(res, dict)):
            return res, False, False
        # 返回是个对象，那么就是ai
        usage = content = data = None
        try:
            if self.provider == 'openai':
                # openai 格式处理
                usage = res['usage']
                content = res['choices'][0]['message']['content']
                # _logger.warning('===========Ai响应:%s' % content)
            elif self.provider == 'azure':
                # azure 格式
                usage = res['usage']
                content = res['choices'][0]['message']['content']
            else:
                usage = False
                content = res
            data = content.replace(' .', '.').strip()
            return data, usage, True
        except Exception as e:
            _logger.error('==========app_chatgpt get_ai_post Error: %s' % e)
            return res, False, False
    
    def get_ai_system(self, content=None):
        # 获取基础ai角色设定, role system
        sys_content = content or self.sys_content
        if sys_content:
            return {"role": "system", "content": sys_content}
        return {}
    
    def get_ai_model_info(self):
        self.ensure_one()
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.openapi_api_key}"}
        R_TIMEOUT = self.ai_timeout or 120
        o_url = "https://api.openai.com/v1/models/%s" % self.ai_model
        if self.endpoint:
            o_url = self.endpoint.replace("/chat/completions", "") + "/models/%s" % self.ai_model
        
        response = requests.get(o_url, headers=headers, timeout=R_TIMEOUT)
        response.close()
        if response:
            res = response.json()
            r_text = json.dumps(res, indent=2)
        else:
            r_text = 'No response.'
        raise UserError(r_text)

    def get_ai_list_model(self):
        self.ensure_one()
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.openapi_api_key}"}
        R_TIMEOUT = self.ai_timeout or 120
        o_url = "https://api.openai.com/v1/models"
        if self.endpoint:
            o_url = self.endpoint.replace("/chat/completions", "") + "/models"
        response = requests.get(o_url, headers=headers, timeout=R_TIMEOUT)
        response.close()
        if response:
            res = response.json()
            r_text = json.dumps(res, indent=2)
        else:
            r_text = 'No response.'
        raise UserError(r_text)

    def get_openai(self, data, author_id, answer_id, param={}):
        self.ensure_one()
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.openapi_api_key}"}
        R_TIMEOUT = self.ai_timeout or 120
        o_url = self.endpoint or "https://api.openai.com/v1/chat/completions"

        # 处理传参，传过来的优先于 robot 默认的
        max_tokens = param.get('max_tokens') if param.get('max_tokens') else self.max_tokens
        temperature = param.get('temperature') if param.get('temperature') else self.temperature
        top_p = param.get('top_p') if param.get('top_p') else self.top_p
        frequency_penalty = param.get('frequency_penalty') if param.get('frequency_penalty') else self.frequency_penalty
        presence_penalty = param.get('presence_penalty') if param.get('presence_penalty') else self.presence_penalty
        request_timeout = param.get('request_timeout') if param.get('request_timeout') else self.ai_timeout
        
        if self.stop:
            stop = self.stop.split(',')
        else:
            stop = ["Human:", "AI:"]
        # 以下处理 open ai
        if self.ai_model == 'dall-e2':
            # todo: 处理 图像引擎，主要是返回参数到聊天中
            # image_url = response['data'][0]['url']
            # https://platform.openai.com/docs/guides/images/introduction
            pdata = {
                "prompt": data,
                "n": 3,
                "size": "1024x1024",
            }
            return '建设中'
        else:
            pdata = {
                "model": self.ai_model,
                "prompt": data,
                "temperature": 1,
                "max_tokens": max_tokens,
                "top_p": 0.6,
                "frequency_penalty": 0.1,
                "presence_penalty": 0.1,
                "stop": stop
            }
            client = OpenAI(
                api_key=self.openapi_api_key,
                timeout=R_TIMEOUT
                )
            response = client.chat.completions.create(
                messages=data,
                model=self.ai_model,
            )
            res = response.model_dump()
            if 'choices' in res:
                return res
            else:
                _logger.warning('=====================openai output data: %s' % response.json())
    
        return _("Response Timeout, please speak again.")

    def get_azure(self, data, author_id, answer_id, param={}):
        self.ensure_one()
        # only for azure
        if not self.endpoint:
            raise UserError(_("Please Set your AI robot's endpoint first."))
        
        if not self.api_version:
            raise UserError(_("Please Set your AI robot's API Version first."))
        
        if self.stop:
            stop = self.stop.split(',')
        else:
            stop = ["Human:", "AI:"]
        if isinstance(data, list):
            messages = data
        else:
            messages = [{"role": "user", "content": data}]

        # 处理传参，传过来的优先于 robot 默认的
        max_tokens = param.get('max_tokens') if param.get('max_tokens') else self.max_tokens
        temperature = param.get('temperature') if param.get('temperature') else self.temperature
        top_p = param.get('top_p') if param.get('top_p') else self.top_p
        frequency_penalty = param.get('frequency_penalty') if param.get('frequency_penalty') else self.frequency_penalty
        presence_penalty = param.get('presence_penalty') if param.get('presence_penalty') else self.presence_penalty
        request_timeout= param.get('request_timeout') if param.get('request_timeout') else self.ai_timeout

        # Ai角色设定，如果没设定则再处理
        if messages[0].get('role') != 'system':
            sys_content = self.get_ai_system(param.get('sys_content'))
            if sys_content:
                messages.insert(0, sys_content)
        #         暂时不变
        
        client = AzureOpenAI(
            api_version=self.api_version,
            azure_endpoint=self.endpoint,
            api_key=self.openapi_api_key,
            timeout=request_timeout
        )
        response = client.chat.completions.create(
            model=self.engine,
            messages=messages,
            # 返回的回答数量
            n=1,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty,
            stop=None,
        )
        res = response.model_dump()
        if 'choices' in res:
            return res
        else:
            _logger.warning('=====================azure output data: %s' % response.json())
        return _("Response Timeout, please speak again.")

    @api.onchange('provider')
    def _onchange_provider(self):
        if self.provider == 'openai':
            self.endpoint = 'https://api.openai.com/v1/chat/completions'
        elif self.provider == 'azure':
            self.endpoint = 'https://odoo.openai.azure.com'
            
        if self.provider:
            # 取头像
            module_path = modules.get_module_path('app_chatgpt', display_warning=False)
            if module_path:
                path = modules.check_resource_path(module_path, ('static/description/src/%s.png' % self.provider))
                if path:
                    image_file = tools.file_open(path, 'rb')
                    self.image_avatar = base64.b64encode(image_file.read())
            
    @api.onchange('set_ai_model')
    def _onchange_set_ai_model(self):
        if self.set_ai_model:
            self.ai_model = self.set_ai_model
        else:
            self.ai_model = None
