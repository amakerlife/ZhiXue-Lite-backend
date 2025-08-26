from io import BytesIO
from typing import Tuple, cast

import requests
from PIL import Image, ImageDraw, ImageFont

from app.config import config
from app.models.exceptions import ZhixueError

font_path = config.FONT_PATH

def get_size(text: str, font: ImageFont.FreeTypeFont) -> Tuple[float, float]:
    """获取文本的宽度和高度"""
    left, top, right, bottom = font.getbbox(text, "utf-8")
    width = right - left
    height = bottom - top
    return width, height


def check_multiple(student_answer_str: str, standard_answer_str: str) -> int:
    """
    检查多选题答案是否正确

    Args:
        student_answer_str: 学生答案
        standard_answer_str: 标准答案

    Returns:
        0: 正确
        1: 少选
        2: 多选
    """
    student_answer = set(student_answer_str)
    standard_answer = set(standard_answer_str)
    if student_answer == standard_answer:
        return 0
    elif student_answer.issubset(standard_answer):
        return 1
    else:
        return 2


def vertical_concat(image_list: list[Image.Image]) -> Image.Image:
    """
    将多个 Image 对象垂直拼接
    """
    widths, heights = zip(*(i.size for i in image_list))
    total_width = max(widths)
    total_height = sum(heights)

    new_im = Image.new("RGB", (total_width, total_height))

    y_offset = 0
    for im in image_list:
        new_im.paste(im, (0, y_offset))
        y_offset += im.size[1]

    return new_im


def draw_details(
    image: Image.Image,
    text: str,
    font: ImageFont.FreeTypeFont,
    x: float,
    y: float,
    color: str,
    cnt: int,
) -> Tuple[Image.Image, int]:
    draw = ImageDraw.Draw(image)
    draw.text((x + 5, y + 10 + cnt), text, fill=color, font=font)
    cnt += 30
    return image, cnt


def draw_answersheet(
    topic_mapping: dict[str, str],
    page_positions: dict[int, list[dict[str, int | list[int]]]],
    objective_answer: dict[int, dict[str, str]],
    answer_details: dict[int, dict[str,
                                   str |
                                   float |
                                   list[dict[str, int | float | list[dict[str, float | str]]]]
                                   ]],
    sheet_images: list[str],
    paper_type: str,
    is_absolute: bool
) -> Image.Image:
    images = []
    for i, image_url in enumerate(sheet_images):
        response = requests.get(image_url)
        image = Image.open(BytesIO(response.content))
        image = image.convert("RGB")
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype(font_path, 25, encoding="utf-8")

        image_width, image_height = image.size

        if paper_type == "A3":
            paper_width, paper_height = 420, 297
        elif paper_type == "A4":
            paper_width, paper_height = 210, 297
        else:
            raise ZhixueError("Unknown paper type")

        for position in page_positions[i]:
            # 计算矩形坐标
            left = cast(int, position["left"])
            top = cast(int, position["top"])
            width = cast(int, position["width"])
            height = cast(int, position["height"])

            if not is_absolute:  # 缩放相对坐标
                left = left * image_width / paper_width
                top = top * image_height / paper_height
                width = width * image_width / paper_width
                height = height * image_height / paper_height

            right = left + width
            bottom = top + height
            problems = cast(list[int], position["ixList"])

            # 绘制选择题每小题得分
            sum_score, standard_sum_score = 0.0, 0.0
            for j, problem in enumerate(problems):
                if problem in objective_answer:
                    student_answer = objective_answer[problem]["answer"]
                    std_answer = objective_answer[problem]["standardAnswer"]
                    if check_multiple(student_answer, std_answer) == 0:
                        draw.text((left + 5, top + 10 + 27 * j),
                                  (f"{topic_mapping.get(str(problem))}: "
                                   f"{student_answer}"), fill="green", font=font)
                    elif check_multiple(student_answer, std_answer) == 1:
                        draw.text((left + 5, top + 10 + 27 * j),
                                  (f"{topic_mapping.get(str(problem))}: "
                                   f"{std_answer}({student_answer})"),
                                  fill="darkorange", font=font)
                    else:
                        draw.text((left + 5, top + 10 + 27 * j),
                                  (f"{topic_mapping.get(str(problem))}: "
                                   f"{std_answer}({student_answer})"),
                                  fill="red", font=font)
                    sum_score += cast(float, answer_details[problem]["score"])
                    standard_sum_score += cast(
                        float,
                        answer_details[problem]["standardScore"]
                    )

            # 绘制主观题各题目得分及阅卷老师
            cnt = 0
            for topic_number, details in answer_details.items():
                if (topic_number in problems
                        and topic_number not in objective_answer):
                    sum_score += cast(float, details["score"])
                    standard_sum_score += cast(float, details["standardScore"])
                    score_text = (
                        f"{topic_mapping.get(str(topic_number))}: 得分: "
                        f"{details['score']}/{details['standardScore']}"
                    )
                    if details['score'] == details['standardScore']:
                        image, cnt = draw_details(
                            image, score_text, font, left, top, "green", cnt
                        )
                    elif details['score'] == 0:
                        image, cnt = draw_details(
                            image, score_text, font, left, top, "red", cnt
                        )
                    else:
                        image, cnt = draw_details(
                            image,
                            score_text,
                            font,
                            left,
                            top,
                            "darkorange",
                            cnt
                        )
                    if len(cast(list, details["subTopics"])) > 1:
                        for subtopic in cast(list, details["subTopics"]):
                            score_text = (
                                f"小题 {subtopic['subTopicIndex']}: 得分: "
                                f"{subtopic['score']}"
                            )
                            image, cnt = draw_details(
                                image, score_text, font, left, top, "blue", cnt
                            )
                            for record in subtopic["teacherMarkingRecords"]:
                                teacher_name = record.get(
                                    "teacherName",
                                    "未知教师"
                                )
                                if teacher_name == "":
                                    teacher_name = "未知教师"
                                image, cnt = draw_details(
                                    image,
                                    f"{teacher_name} 打分: {record['score']}",
                                    font,
                                    left,
                                    top,
                                    "blue",
                                    cnt
                                )
                    elif (isinstance(details["subTopics"], list) and
                          details["subTopics"]):
                        subtopic = cast(dict, details["subTopics"][0])
                        for record in subtopic["teacherMarkingRecords"]:
                            teacher_name = record.get("teacherName", "未知教师")
                            image, cnt = draw_details(
                                image,
                                f"{teacher_name} 打分: {record['score']}",
                                font,
                                left,
                                top,
                                "blue",
                                cnt
                            )

            # 绘制区域边框及总分
            text_content = f"{sum_score}/{standard_sum_score}"
            text_width, text_height = get_size(text_content, font)
            color, text_color = "", ""
            if sum_score == standard_sum_score:
                color, text_color = "green", "green"
            elif sum_score == 0:
                color, text_color = "red", "red"
            else:
                color, text_color = "orange", "darkorange"
            draw.rectangle([left, top, right, bottom], outline=color, width=5)
            draw.text((right - 5 - text_width, bottom - 10 - text_height),
                      text_content, fill=text_color, font=font)

        images.append(image)
    all_image = vertical_concat(images)

    # 计算总分
    all_score = 0
    standard_all_score = 0
    for details in answer_details.values():
        all_score += cast(float, details["score"])
        standard_all_score += cast(float, details["standardScore"])

    draw = ImageDraw.Draw(all_image)
    font = ImageFont.truetype(font_path, 50, encoding="utf-8")
    draw.text(
        (10, 10),
        f"{all_score}/{standard_all_score}",
        fill="red", font=font
    )
    draw.text(
        (10, 70),
        "本答题卡数据仅供参考，请以智学网分数为准",
        fill="blue", font=font)

    return all_image
