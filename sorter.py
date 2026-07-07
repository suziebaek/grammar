# sorter.py

def get_sorted_q_nums(q_keys, all_qtype_map, all_diff_map, is_diff_sort):
    """
    생성된 문제의 고유 번호(Keys)들을 받아, 선택된 모드에 따라 정렬된 순서를 반환합니다.
    """
    keys_list = list(q_keys)

    if is_diff_sort:
        # [난이도별 정렬 모드]
        # 1. 파이썬의 sort는 안정 정렬(Stable Sort)이므로, 먼저 '유형별'로 정렬해 둡니다.
        # 이렇게 하면 나중에 난이도로 묶었을 때, 같은 난이도 안에서 유형이 섞이지 않고 예쁘게 뭉칩니다.
        keys_list.sort(key=lambda k: all_qtype_map.get(k, ""))

        # 2. 난이도 우선순위 매핑 (상 -> 중 -> 하 순서로 끌어올림)
        # E레벨(7~9점)이든 H레벨(6~7점)이든 상관없이 '상' 라벨 하나로 완벽히 통제됩니다.
        diff_priority = {"상": 0, "중": 1, "하": 2}
        keys_list.sort(key=lambda k: diff_priority.get(all_diff_map.get(k, ""), 3))

    else:
        # [유형별 정렬 모드 (기본)]
        # 생성될 때부터 유형별로 global_q_num이 부여되었으므로 숫자 크기대로 오름차순 정렬
        keys_list.sort()

    return keys_list
