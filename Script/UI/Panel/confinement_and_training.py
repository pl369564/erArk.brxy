from typing import List
from types import FunctionType
from Script.Core import cache_control, game_type, get_text, flow_handle, constant, py_cmd
from Script.Design import handle_premise, handle_instruct, attr_calculation, game_time, map_handle
from Script.UI.Moudle import draw, panel
from Script.Config import game_config, normal_config
import random

cache: game_type.Cache = cache_control.cache
""" 游戏缓存数据 """
_: FunctionType = get_text._
""" 翻译api """
line_feed = draw.NormalDraw()
""" 换行绘制对象 """
line_feed.text = "\n"
line_feed.width = 1
window_width: int = normal_config.config_normal.text_width
""" 窗体宽度 """


def settle_prisoners():
    """
    囚犯结算，先计算逃脱概率的增加，再判断是否能逃脱，最后处理失败与成功的情况。\n
    """
    for character_id in cache.rhodes_island.current_prisoners:
        # 计算逃脱概率
        escape_probability = calculate_escape_probability(character_id)
        # 判断是否能逃脱
        can_escape, escape_value, warden_value = judge_can_escape(character_id)
        # 逃脱成功
        if can_escape:
            escape_success(character_id)
        # 逃脱失败
        else:
            escape_fail(character_id)

def calculate_escape_probability(character_id: int) -> float:
    """
    计算指定角色的逃脱概率。\n
    逃脱概率 = (战斗技能 + 学识技能) * (confinement_training_setting[4] * 0.5)\n
    战斗技能存储在 character_data.ability[42]，学识技能存储在 character_data.ability[45]。\n
    计算得到的概率将记录在 cache.rhodes_island.current_prisoners[chara_id][1]。\n
    Keyword arguments:\n
    character_id -- 角色id\n
    Return arguments:\n
    float -- 逃脱概率\n
    """

    character_data = cache.character_data[character_id]

    # 战斗和学识技能
    combat_skill = character_data.ability[42]
    knowledge_skill = character_data.ability[45]
    total_skill = combat_skill + knowledge_skill

    # 基础系数基于生活水平
    coefficient = (cache.rhodes_island.confinement_training_setting.get(4, 0) + 1) * 0.5
    # 屈服刻印减少系数
    coefficient -= character_data.ability[14] * 0.1
    # 反发刻印增加系数
    coefficient += character_data.ability[18] * 0.2
    # 陷落降低系数
    now_fall = attr_calculation.get_character_fall_level(character_id)
    coefficient -= now_fall * 0.2
    # 乘以系数后的逃脱概率
    add_escape_probability = total_skill * coefficient

    # 已逃脱概率越高，则越难提升
    max_probability = (100 - cache.rhodes_island.current_prisoners[character_id][1]) * 0.1
    add_escape_probability = int(min(add_escape_probability, max_probability))

    # 记录逃脱概率
    if character_id in cache.rhodes_island.current_prisoners:
        cache.rhodes_island.current_prisoners[character_id][1] += add_escape_probability
        cache.rhodes_island.current_prisoners[character_id][1] = min(cache.rhodes_island.current_prisoners[character_id][1], 100)
    else:
        cache.rhodes_island.current_prisoners[character_id] = [cache.game_time, add_escape_probability]

    return add_escape_probability

def judge_can_escape(character_id: int) -> bool:
    """
    判断指定角色是否能逃脱成功。\n
    逃脱成功条件：\n
    1. 逃脱概率大于80\n
    2. 如果存在监狱长，则需要对比逃脱角色和监狱长的战斗技能与体力气力\n
    Keyword arguments:\n
    character_id -- 角色id\n
    Return arguments:\n
    bool -- 是否逃脱成功\n
    float -- 囚犯逃脱值\n
    float -- 监狱长对抗值\n
    """
    # 需要是囚犯
    if character_id not in cache.rhodes_island.current_prisoners:
        return False, 0, 0
    # 如果没有监狱长，且概率大于30，则直接逃脱
    warden_id = cache.rhodes_island.current_warden_id
    if warden_id == 0:
        if cache.rhodes_island.current_prisoners[character_id][1] > 30:
            return True, 0, 0
        return False, 0, 0
    # 需要逃脱概率大于80
    if cache.rhodes_island.current_prisoners[character_id][1] < 80:
        return False, 0, 0

    # 囚犯的逃脱概率
    character_data = cache.character_data[character_id]
    escape_value = cache.rhodes_island.current_prisoners[character_id][1] / 100
    # 乘以生活水平
    escape_value *= (cache.rhodes_island.confinement_training_setting[4] + 1) * 0.4
    # 乘以战斗技能
    escape_value *= character_data.ability[42]
    # 乘以体力气力
    escape_value *= character_data.hit_point / 100
    escape_value *= character_data.mana_point / 100

    # 监狱长的对抗值
    warden_data = cache.character_data[warden_id]
    warden_value = warden_data.ability[42]
    warden_value *= warden_data.hit_point / 100
    warden_value *= warden_data.mana_point / 100

    # 对比
    if escape_value > warden_value:
        return True, escape_value, warden_value
    return False, escape_value, warden_value

def escape_success(character_id: int):
    """
    逃脱成功处理。\n
    Keyword arguments:\n
    character_id -- 角色id\n
    """
    from Script.Settle import default
    character_data = cache.character_data[character_id]
    # 逃脱成功提示
    escape_text = _("\n囚犯{0}逃脱成功，请尽快派遣外勤干员进行追捕！\n").format(character_data.name)
    escape_draw = draw.WaitDraw()
    escape_draw.text = escape_text
    escape_draw.style = 'warning'
    escape_draw.width = window_width
    escape_draw.draw()
    # 移除囚犯信息
    cache.rhodes_island.current_prisoners.pop(character_id)
    # 囚犯离线
    default.handle_chara_off_line(character_id, 1, change_data = game_type.CharacterStatusChange, now_time = cache.game_time)

def escape_fail(character_id: int):
    """
    逃脱失败处理。\n
    Keyword arguments:\n
    character_id -- 角色id\n
    """
    character_data = cache.character_data[character_id]
    # 逃脱失败提示
    escape_text = _("囚犯{0}逃脱失败，监狱长已经加强了对其的监视！\n").format(character_data.name)
    escape_draw = draw.NormalDraw()
    escape_draw.text = escape_text
    escape_draw.style = 'gold_enrod'
    escape_draw.width = window_width
    escape_draw.draw()
    # 囚犯逃脱值清零
    cache.rhodes_island.current_prisoners[character_id][1] = 0

def chara_become_prisoner(character_id: int):
    """
    角色成为囚犯，不含位置和上线结算\n
    Keyword arguments:\n
    character_id -- 角色id\n
    """
    from Script.Design import clothing
    character_data = cache.character_data[character_id]

    # flag结算
    character_data.sp_flag.be_bagged = 0
    character_data.sp_flag.imprisonment = 1
    # 重置身体管理
    character_data.body_manage = attr_calculation.get_body_manage_zero()
    # 加入囚犯数据
    cache.rhodes_island.current_prisoners[character_id] = [cache.game_time, 0]
    # 服装结算
    clothing.handle_prisoner_clothing(character_id)
    # 当前位置作为宿舍，并保存旧宿舍
    if character_data.pre_dormitory == "":
        character_data.pre_dormitory = character_data.dormitory
    character_data.dormitory = map_handle.get_map_system_path_str_for_list(character_data.position)
    # 给予屈服2，恐怖1，反发3，但如果有隶属系陷落，则可以减轻该效果
    target_fall = attr_calculation.get_character_fall_level(character_id, minus_flag=True)
    if character_data.ability[14] <= 1:
        character_data.ability[14] = 2
        character_data.second_behavior[1034] = 1
    if character_data.ability[17] <= 0 and target_fall >= -2:
        character_data.ability[17] = 1
        character_data.second_behavior[1042] = 1
    if character_data.ability[18] <= 0 and target_fall >= -2:
        character_data.ability[18] = 1
        character_data.second_behavior[1045] = 1
    if character_data.ability[18] <= 1 and target_fall >= -1:
        character_data.ability[18] = 2
        character_data.second_behavior[1046] = 1
    if character_data.ability[18] <= 2 and target_fall >= 0:
        character_data.ability[18] = 3
        character_data.second_behavior[1047] = 1

def get_unused_prison_dormitory() -> str:
    """
    遍历当前所有囚犯，从其角色属性中读取宿舍位置，
    根据预设的所有牢狱列表，选取还没有被使用的牢狱，
    返回该牢狱的名字。如果所有牢狱都已被占用，则返回空字符串。

    Return:
        str -- 可用牢狱的名字，如果没有可用牢狱则返回空字符串
    """
    # 预设的所有牢狱名字列表
    all_dormitories = ['牢1', '牢2', '牢3', '牢4', '牢5', '牢6', '牢7', '牢8']

    # 收集所有在用的牢狱名字
    occupied_dorms = set()
    for prisoner_id in cache.rhodes_island.current_prisoners:
        character_data = cache.character_data[prisoner_id]
        dorm = character_data.dormitory
        for d in all_dormitories:
            if d in dorm:
                occupied_dorms.add(d)

    # 选取一个未被占用的牢狱
    for dorm in all_dormitories:
        if dorm not in occupied_dorms:
            return dorm
    return ""

class Confinement_And_Training_Manage_Panel:
    """
    用于监禁调教管理的面板对象
    Keyword arguments:
    width -- 绘制宽度
    """

    def __init__(self, width: int):
        """初始化绘制对象"""
        self.width: int = width
        """ 绘制的最大宽度 """
        self.now_panel = _("监禁调教管理")
        """ 当前绘制的页面 """
        self.draw_list: List[draw.NormalDraw] = []
        """ 绘制的文本列表 """
        self.pl_character_data = cache.character_data[0]
        """ 玩家的角色数据 """
        self.done_training_status_id_set = set()
        """ 已经调教过的状态id集合 """

    def draw(self):
        """绘制对象"""

        title_text = _("监禁调教管理")
        title_draw = draw.TitleLineDraw(title_text, self.width)
        while 1:
            return_list = []
            title_draw.draw()

            # 输出提示信息
            now_draw = draw.NormalDraw()
            info_text = _(" \n ○点击[选项标题]显示[选项介绍]，点击[选项本身]即可[改变该选项]\n")
            now_draw.text = info_text
            now_draw.width = self.width
            now_draw.draw()

            # 遍历全部设置
            for cid in game_config.config_confinement_training_setting:
                line_feed.draw()
                confinement_training_setting_data = game_config.config_confinement_training_setting[cid]
                # 选项名
                # id_text = f"[{(str(cid)).rjust(2, '0')}]"
                button_text = f"  [{confinement_training_setting_data.name}]： "
                button_len = max(len(button_text) * 2, 60)
                button_draw = draw.LeftButton(button_text, button_text, button_len, cmd_func=self.draw_info, args=(cid))
                button_draw.draw()
                return_list.append(button_draw.return_text)

                # 如果没有该键，则创建一个，并置为0
                if cid not in cache.rhodes_island.confinement_training_setting:
                    cache.rhodes_island.confinement_training_setting[cid] = 0
                now_setting_flag = cache.rhodes_island.confinement_training_setting[cid] # 当前设置的值
                option_len = len(game_config.config_confinement_training_setting_option[cid]) # 选项的长度

                # 当前选择的选项的名字
                button_text = f" [{game_config.config_confinement_training_setting_option[cid][now_setting_flag]}] "
                button_len = max(len(button_text) * 2, 20)

                # 绘制选项
                if cid not in {11}:
                    button_draw = draw.LeftButton(button_text, str(cid) + button_text, button_len, cmd_func=self.change_setting, args=(cid, option_len))
                    button_draw.draw()
                    return_list.append(button_draw.return_text)
                # 调教前准备单独处理
                elif cid == 11:
                    clean_flag = cache.rhodes_island.pre_training_cleaning
                    lubrication_flag = cache.rhodes_island.pre_training_lubrication
                    tool_dict = cache.rhodes_island.pre_training_tool_dict

                    if clean_flag:
                        clean_text = _(" [进行污浊清洗] ")
                    else:
                        clean_text = _(" [不进行污浊清洗] ")
                    clean_button = draw.LeftButton(clean_text, _("污浊清洗"), len(clean_text) * 2, cmd_func=self.change_pre_training_cleaning)
                    clean_button.draw()
                    return_list.append(clean_button.return_text)
                    if lubrication_flag:
                        lubrication_text = _(" [使用润滑液提前润滑] ")
                    else:
                        lubrication_text = _(" [不使用润滑液提前润滑] ")
                    lubrication_button = draw.LeftButton(lubrication_text, _("润滑液"), len(lubrication_text) * 2, cmd_func=self.change_pre_training_lubrication)
                    lubrication_button.draw()
                    return_list.append(lubrication_button.return_text)
                    tool_text = _(" [调整道具使用] ")
                    tool_button = draw.LeftButton(tool_text, _("道具使用"), len(tool_text) * 2, cmd_func=self.adjust_tool_list)
                    tool_button.draw()
                    return_list.append(tool_button.return_text)

            line_feed.draw()
            back_draw = draw.CenterButton(_("[返回]"), _("返回"), window_width)
            back_draw.draw()
            line_feed.draw()
            return_list.append(back_draw.return_text)
            yrn = flow_handle.askfor_all(return_list)
            if yrn == back_draw.return_text:
                cache.now_panel_id = constant.Panel.IN_SCENE
                break

    def draw_info(self, cid: int):
        """绘制设置的详细信息"""
        line = draw.LineDraw("-", self.width)
        line.draw()
        now_draw = draw.WaitDraw()
        setting_data = game_config.config_physical_exam_setting[cid]
        info_text = f"\n {setting_data.info}\n"
        now_draw.text = info_text
        now_draw.width = self.width
        now_draw.draw()
        line = draw.LineDraw("-", self.width)
        line.draw()

    def change_setting(self, cid, option_len):
        """修改设置"""
        if cache.rhodes_island.confinement_training_setting[cid] < option_len - 1:
            cache.rhodes_island.confinement_training_setting[cid] += 1
        else:
            cache.rhodes_island.confinement_training_setting[cid] = 0

    def change_pre_training_cleaning(self):
        """切换是否进行污浊清洗"""
        cache.rhodes_island.pre_training_cleaning = not cache.rhodes_island.pre_training_cleaning

    def change_pre_training_lubrication(self):
        """切换是否使用润滑液提前润滑"""
        cache.rhodes_island.pre_training_lubrication = not cache.rhodes_island.pre_training_lubrication

    def adjust_tool_list(self):
        """调整道具使用"""
        from Script.UI.Panel import h_item_shop_panel
        body_item_list = h_item_shop_panel.body_item_list

        while 1:
            return_list = []
            line = draw.LineDraw("-", self.width)
            line.draw()
            line_feed.draw()
            # 输出提示信息
            info_draw = draw.NormalDraw()
            info_text = _("○开启后，监狱长会在进行调教准备时依次使用选择道具\n")
            info_text += _("○消耗类道具会在使用时减少，数量不足时会自动关闭\n")
            info_draw.text = info_text
            info_draw.width = self.width
            info_draw.draw()
            line_feed.draw()

            # 遍历道具列表
            for i in range(len(body_item_list)):
                # 初始化道具字典
                if i not in cache.rhodes_island.pre_training_tool_dict:
                    cache.rhodes_island.pre_training_tool_dict[i] = 0

                # 持有道具数量
                item_id = h_item_shop_panel.get_item_id_from_body_item_list(i)
                item_num = cache.character_data[0].item[item_id]
                name_draw_text = f"[{(str(i)).rjust(2, '0')}]"
                len_add = 40 - len(body_item_list[i]) # 排版用的空格数量
                if i in {2, 3}:
                    len_add += 1
                # 如果是消耗类道具，显示数量
                if i in {8, 9, 10, 11, 12, 13}:
                    name_draw_text += f"{body_item_list[i]}(有{item_num}个) "
                    len_add += 1
                # 否则只显示是否持有
                else:
                    name_draw_text += f"{body_item_list[i]}"
                    if item_num > 0:
                        name_draw_text += _("(已持有)")
                    else:
                        name_draw_text += _("(未持有)")
                # 给name_draw_text从右侧补空格到40个字符
                name_draw_text = name_draw_text.ljust(len_add, " ")

                # 绘制道具名
                name_draw = draw.NormalDraw()
                name_draw.text = name_draw_text
                name_draw.width = len(name_draw_text)
                name_draw.draw()

                # 如果数量为0，则绘制灰色不可选按钮
                if item_num <= 0:
                    cache.rhodes_island.pre_training_tool_dict[i] = 0
                    button_text = _(" [不使用] ")
                    button_draw = draw.NormalDraw()
                    button_draw.text = button_text
                    button_draw.style = 'deep_gray'
                    button_draw.width = 20
                    button_draw.draw()
                else:
                    if cache.rhodes_island.pre_training_tool_dict[i]:
                        button_text = _(" [使用] ")
                    else:
                        button_text = _(" [不使用] ")
                    button_draw = draw.LeftButton(button_text, str(i) + button_text, 20, cmd_func=self.change_pre_training_tool, args=(i,))
                    button_draw.draw()
                    return_list.append(button_draw.return_text)
                line_feed.draw()

            line_feed.draw()
            back_draw = draw.CenterButton(_("[返回]"), _("返回"), window_width)
            back_draw.draw()
            return_list.append(back_draw.return_text)
            line_feed.draw()

            yrn = flow_handle.askfor_all(return_list)
            if yrn == back_draw.return_text:
                break

    def change_pre_training_tool(self, tool_id: int):
        """切换是否使用道具"""
        if cache.rhodes_island.pre_training_tool_dict[tool_id]:
            cache.rhodes_island.pre_training_tool_dict[tool_id] = 0
        else:
            cache.rhodes_island.pre_training_tool_dict[tool_id] = 1

    def adjust_target_list(self):
        """调整体检对象名单"""
        from Script.UI.Panel import normal_panel
        now_draw_panel : panel.PageHandlePanel = panel.PageHandlePanel([], normal_panel.CommonSelectNPCButtonList, 50, 5, window_width, 1, 0, 0)
        while 1:
            npc_id_got_list = sorted(cache.npc_id_got)
            # 已选择的角色id列表
            selected_id_list = list(cache.rhodes_island.manually_selected_exam_operator_ids)
            final_list = []
            # 遍历角色id
            for npc_id in npc_id_got_list:
                if npc_id == 0:
                    continue
                now_list = [npc_id, self.switch_chara_in_target_list, selected_id_list]
                final_list.append(now_list)
            now_draw_panel.text_list = final_list

            # 调用通用选择按钮列表函数
            return_list = normal_panel.common_select_npc_button_list_func(now_draw_panel, _("体检对象名单"))

            yrn = flow_handle.askfor_all(return_list)
            if yrn == _("返回"):
                break

    def switch_chara_in_target_list(self, character_id: int):
        """切换体检对象名单中的角色"""
        if character_id in cache.rhodes_island.manually_selected_exam_operator_ids:
            cache.rhodes_island.manually_selected_exam_operator_ids.remove(character_id)
        else:
            cache.rhodes_island.manually_selected_exam_operator_ids.add(character_id)
