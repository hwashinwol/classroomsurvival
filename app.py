import random
import time
import os
import sqlite3
from datetime import datetime
import streamlit as st
import pandas as pd

st.set_page_config(page_title = 'Survival Game', page_icon = '💀', layout = 'centered')

class GameDB:
    def __init__(self, db_name = 'survival_game.db'):
        self.db_name = db_name
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS game_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    play_date TEXT,
                    result TEXT,
                    days_survived INTEGER,
                    score INTEGER,
                    full_log TEXT
                )
            ''')
            conn.commit()

    def save_record(self, result, days, score, logs): # score 자리 추가
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            play_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_text = "\n".join(logs)

            cursor.execute('''
                INSERT INTO game_history (play_date, result, days_survived, score, full_log)
                VALUES (?, ?, ?, ?, ?)                             
            ''', (play_date, result, days, score, log_text)) 
            conn.commit()
            print(f"[System] 데이터베이스에 기록이 저장되었습니다. (ID : {cursor.lastrowid})")

    def get_ranking_df(self):
        with sqlite3.connect(self.db_name) as conn:
            df = pd.read_sql_query('''
                SELECT 
                    dense_rank() OVER (ORDER BY score DESC) as 순위,
                    days_survived || '일차' as 생존기간,
                    score as 점수,
                    result as 결과,
                    substr(play_date, 1, 10) as 날짜
                FROM game_history
                ORDER BY score DESC
                LIMIT 10
            ''', conn)
        return df                            

if 'init' not in st.session_state:
    st.session_state.init = True
    st.session_state.phase = 'START' 
    st.session_state.survivors = 50
    st.session_state.day = 1
    st.session_state.tokens = 15
    st.session_state.score = 0
    st.session_state.logs = []
    st.session_state.posture = 0 
    st.session_state.player_id = 0 # 플레이어 번호
    st.session_state.db = GameDB()
    st.session_state.last_msg = ""

POSTURES = [
    "자리에 정자세로 앉음", 
    "책상 위에 엎드림", 
    "책상 밑으로 숨음", 
    "의자 밑으로 웅크림", 
    "바닥에 주저앉음", 
    "바닥에 완전히 엎드리기"
]

# ==========================================
# 3. 헬퍼 함수
# ==========================================
def show_status_bar():
    with st.container():
        c1, c2, c3 = st.columns(3)
        c1.metric("👥 생존자", f"{st.session_state.survivors}명")
        c2.metric("💰 토큰", f"{st.session_state.tokens}개")
        c3.metric("🏆 점수", f"{st.session_state.score}점")
        st.divider()

def add_log(text):
    st.session_state.logs.append(f"Day {st.session_state.day}: {text}")

def reset_game():
    st.session_state.phase = 'DAY'
    st.session_state.survivors = 30
    st.session_state.day = 1
    st.session_state.tokens = 10
    st.session_state.score = 0
    st.session_state.logs = []
    st.session_state.posture = 0
    st.session_state.last_msg = f"게임이 시작되었습니다. \n 현재 생존자 수 : {st.session_state.survivors}명"

# ==========================================
# 4. 화면 구성 (UI)
# ==========================================

# [메인] 타이틀
st.title("💀 생존 게임: The Survivor")

# ------------------------------------------
# Phase 1: 시작 화면
# ------------------------------------------
if st.session_state.phase == 'START':
    st.markdown("""
    ### 규칙 설명
    1. 당신은 폐쇄된 교실에 갇혔습니다.
    2. **낮**에는 행동을 선택해 점수와 토큰을 얻습니다.
    3. **밤**에는 괴물에게 토큰을 바쳐야 합니다.
    4. 괴물의 기분을 거스르거나 토큰이 부족하면 **죽습니다.**
    """)
    if st.button("게임 시작", type="primary", use_container_width=True):
        reset_game()
        st.rerun()

# ------------------------------------------
# Phase 2: 낮 (행동 선택)
# ------------------------------------------
elif st.session_state.phase == 'DAY':
    st.subheader(f"☀️ Day {st.session_state.day} - 낮")
    
    if st.session_state.last_msg:
        st.success(st.session_state.last_msg)
        st.session_state.last_msg = "" # 메시지 초기화

    st.write("교실은 고요합니다. 무엇을 하시겠습니까?")

    # 행동 선택지
    action = st.radio(
        "행동을 선택하세요:",
        [
            "1. 자리에 앉아 태블릿 게임 (안전/점수+10)",
            "2. 옆 사람에게 필담 (주의/점수+20)",
            "3. 자리 이동 및 파밍 (위험, 0~2개의 토큰 획득 가능/점수+30)",
            "4. 멍하니 있기 (매우안전/점수+0)"
        ]
    )

    if st.button("행동 결정", type="primary"):
        score_gain = 0
        log_text = ""
        
        if "1." in action:
            score_gain = 10
            log_text = "태블릿 게임 (집중)"
            st.session_state.last_msg = "게임에 집중하며 시간을 보냈습니다."
        elif "2." in action:
            score_gain = 20
            log_text = "옆 사람과 필담"
            st.session_state.last_msg = "옆 사람과 쪽지를 주고받았습니다."
        elif "3." in action:
            score_gain = 20
            found = random.randint(0, 2)
            st.session_state.tokens += found
            log_text = f"자리 이동 (토큰 {found}개 획득)"
            
            # 파밍 결과 메시지 설정
            if found > 0:
                result_msg = f"💎 대박! 위험을 무릅쓰고 토큰 {found}개를 찾았습니다!"
            else:
                result_msg = "💨 위험을 감수하고 돌아다녔지만, 아무것도 없었습니다."
        elif "4." in action:
            score_gain = 0
            log_text = "멍하니 있음"
            st.session_state.last_msg = "체력을 아끼며 가만히 있었습니다."

        st.session_state.score += score_gain
        add_log(f"(낮) {log_text} (+{score_gain}점)")

        with st.spinner("해가 지고 있습니다..."):
            time.sleep(2)
        st.session_state.phase = 'NIGHT'
        st.rerun()

# ------------------------------------------
# Phase 3: 밤 (토큰 제출 & 판정)
# ------------------------------------------
elif st.session_state.phase == 'NIGHT':
    st.subheader(f"🌙 Day {st.session_state.day} - 밤")
    st.error("밤이 되었습니다. 괴물의 그림자가 보입니다...")
    
    # 자세 변경 옵션
    if st.session_state.posture < 5:
        if st.checkbox(f"자세 낮추기 (현재: {POSTURES[st.session_state.posture]})"):
            st.session_state.posture += 1
            st.warning(f"자세를 변경했습니다 -> {POSTURES[st.session_state.posture]}")

    st.markdown("---")
    st.write(f"**보유 토큰: {st.session_state.tokens}개**")
    
    # 토큰 제출 슬라이더
    token_pay = st.number_input("괴물에게 바칠 토큰 수(0~2)", 
                                min_value = 0, 
                                max_value = 2, 
                                value = 0,
                                step = 1)
    
    if st.button("제출하고 기도하기", type="primary"):
        if token_pay > st.session_state.tokens:
            st.error("토큰이 부족합니다!")
        else:
            # 1. 자원 차감
            st.session_state.tokens -= token_pay
            add_log(f"(밤) 토큰 {token_pay}개 제출")

            # 2. 소음 실수 확률
            made_noise = False
            if random.random() < 0.2:
                made_noise = True
                add_log("[실수] 토큰을 떨어뜨려 소리를 냄!")
                st.toast("딸그락! 소리를 냈습니다!", icon="😱")

            # 3. 생존 판정 (로직 복사)
            death_risk = 0
            if made_noise: death_risk += 50
            if token_pay == 0: death_risk += 30
            if random.randint(0, 5) == st.session_state.posture: death_risk += 20
            
            with st.spinner("괴물이 심판 중입니다..."):
                time.sleep(2)

            if random.randint(1, 100) <= death_risk:
                st.session_state.phase = 'ENDING'
                st.session_state.result = 'LOSE'
            else:
                died_npc = random.randint(3, 8) if st.session_state.survivors > 10 else random.randint(2, 6)
                st.session_state.survivors = max(1, st.session_state.survivors - died_npc)
                
                st.session_state.score += 100
                st.session_state.day += 1
                st.session_state.last_msg = f"밤을 무사히 넘겼습니다. (생존 보너스 +100점 / {died_npc}명 사망) \n 남은 생존자 수 : {st.session_state.survivors}명."
                st.session_state.phase = 'DAY'
                
                if st.session_state.survivors <= 1:
                    st.session_state.phase = 'ENDING'
                    st.session_state.result = 'WIN'
                    st.session_state.score += 500 

            st.rerun()

            dice = random.randint(1, 100)
            
            if dice <= death_risk:
                # 사망
                st.session_state.phase = 'ENDING'
                st.session_state.result = 'LOSE'
            else:
                # 생존
                # NPC 사망 처리
                died_npc = random.randint(3, 8) if st.session_state.survivors > 10 else random.randint(1, 6)
                st.session_state.survivors = max(1, st.session_state.survivors - died_npc)
                
                # 점수 보너스
                st.session_state.score += 100
                st.session_state.day += 1
                st.session_state.last_msg = f"밤을 무사히 넘겼습니다. (생존 보너스 +100점 / {died_npc}명 사망)"
                st.session_state.phase = 'DAY'
                
                # 최후의 1인 체크
                if st.session_state.survivors <= 1:
                    st.session_state.phase = 'ENDING'
                    st.session_state.result = 'WIN'
                    st.session_state.score += 500 # 승리 보너스

            st.rerun()

# ------------------------------------------
# Phase 4: 엔딩 & 랭킹
# ------------------------------------------
elif st.session_state.phase == 'ENDING':
    if st.session_state.result == 'WIN':
        st.balloons()
        st.success(f"🏆 축하합니다! 최후의 1인이 되었습니다! (최종 점수: {st.session_state.score}점)")
    else:
        st.snow()
        st.error(f"💀 당신은 괴물에게 선택되었습니다... (최종 점수: {st.session_state.score}점)")
    
    # DB 저장 (중복 저장 방지를 위해 체크)
    if 'saved' not in st.session_state:
        st.session_state.db.save_record(
            st.session_state.result, 
            st.session_state.day, 
            st.session_state.score, 
            st.session_state.logs
        )
        st.session_state.saved = True

    st.markdown("---")
    
    # 랭킹 출력
    st.subheader("🏆 명예의 전당 (Top 10)")
    ranking_df = st.session_state.db.get_ranking_df()
    st.table(ranking_df) # Pandas DataFrame을 예쁜 표로 출력

    col1, col2 = st.columns(2)
    with col1:
        with st.expander("📜 이번 게임의 기록 보기"):
            for log in st.session_state.logs:
                st.text(log)
    
    with col2:
        if st.button("다시 도전하기", type="primary", use_container_width=True):
            if 'saved' in st.session_state:
                del st.session_state.saved 
            reset_game()
            st.rerun()