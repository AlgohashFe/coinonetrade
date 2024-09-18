import streamlit as st
import uuid  # 파일 상단에 이 줄을 추가해주세요


# Streamlit UI 설정
st.set_page_config(layout="wide")

from datetime import datetime, timedelta

import requests
import pandas as pd
import json
import uuid
import base64
import hashlib
import hmac
import httplib2
import time
import math
import json
import os
from datetime import datetime


# 사용자 정보 (토큰 및 키) - secrets.toml에서 가져오기
ACCESS_TOKEN = st.secrets.get("access_key", "")
SECRET_KEY = bytes(st.secrets.get("private_key", ""), 'utf-8')

# 현재 작업 디렉토리 출력
current_directory = os.getcwd()
st.write(f"현재 작업 디렉토리: {current_directory}")


def fetch_order_detail(order_id):
    action = "/v2.1/order/detail"
    payload = {
        "access_token": ACCESS_TOKEN,
        "nonce": str(uuid.uuid4()),
        "order_id": order_id,
        "quote_currency": "KRW",
        "target_currency": "USDT"
    }

    result = get_response(action, payload)

    if result and result.get('result') == 'success':
        return result.get('order')
    else:
        st.error("주문 조회 오류 발생")
        return None

    
def get_encoded_payload(payload):
    payload['nonce'] = str(uuid.uuid4())  # nonce 추가
    dumped_json = json.dumps(payload)
    encoded_json = base64.b64encode(dumped_json.encode('utf-8'))  # UTF-8 인코딩 추가
    return encoded_json.decode('utf-8')  # 결과를 문자열로 디코딩

def get_signature(encoded_payload):
    signature = hmac.new(SECRET_KEY, encoded_payload.encode('utf-8'), hashlib.sha512)  # encoded_payload 인코딩
    return signature.hexdigest()

def get_response(action, payload):
    url = f'https://api.coinone.co.kr{action}'
    encoded_payload = get_encoded_payload(payload)
    headers = {
        'Content-type': 'application/json',
        'X-COINONE-PAYLOAD': encoded_payload,
        'X-COINONE-SIGNATURE': get_signature(encoded_payload),
    }

    http = httplib2.Http()
    response, content = http.request(url, 'POST', body=encoded_payload, headers=headers)

    print(f"HTTP Status Code: {response.status}")
    try:
        json_content = json.loads(content.decode('utf-8'))
        if 'balances' in json_content:
            filtered_balances = [balance for balance in json_content['balances'] if balance['currency'] in ['KRW', 'USDT']]
            json_content['balances'] = filtered_balances
        
        print(f"Filtered Response Content: {json.dumps(json_content, indent=2)}")
        return json_content
    except json.JSONDecodeError:
        print(f"Response Content (raw): {content.decode('utf-8')}")
        return None

    try:
        json_content = json.loads(content.decode('utf-8'))
        if response.status == 200 and json_content.get('result') == 'success':
            return json_content
        else:
            error_code = json_content.get('error_code', 'Unknown error code')
            error_msg = json_content.get('error_msg', 'Unknown error message')
            st.error(f"API 요청 오류: 코드 {error_code}, 메시지: {error_msg}")
            return None
    except json.JSONDecodeError as e:
        st.error(f"JSONDecodeError: {e}")
        st.error(f"Response content: {content.decode('utf-8')}")
        return None
    

def save_log(log_data):
    log_file = 'order_log.json'
    full_path = os.path.join(current_directory, log_file)
    st.write(f"로그 파일 경로: {full_path}")
    
    try:
        if os.path.exists(full_path):
            with open(full_path, 'r') as f:
                logs = json.load(f)
        else:
            logs = []
        
        logs.append(log_data)
        
        with open(full_path, 'w') as f:
            json.dump(logs, f, indent=2)
        
        st.success(f"로그가 성공적으로 저장되었습니다: {full_path}")
        
        # 로그 표시
        st.markdown("### 최근 주문 로그")
        st.write(f"시간: {log_data['timestamp']}")
        st.write(f"주문 유형: {log_data['order_type']}")
        st.write(f"매수/매도: {log_data['side']}")
        st.write(f"가격: {log_data['price']}")
        st.write(f"수량: {log_data['quantity']}")
        st.write(f"상태: {log_data['status']}")
        st.write("---")
        
    except Exception as e:
        st.error(f"로그 저장 중 오류 발생: {str(e)}")
        st.error(f"현재 디렉토리: {current_directory}")
        st.error(f"파일 경로: {full_path}")

        

# 호가 조회 함수
def fetch_order_book():
    url = "https://api.coinone.co.kr/public/v2/orderbook/KRW/USDT?size=5"
    headers = {"accept": "application/json"}
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        if data.get('result') == 'success':
            bids = data.get('bids', [])
            asks = data.get('asks', [])
            bids_df = pd.DataFrame(bids)
            asks_df = pd.DataFrame(asks)

            bids_df['price'] = pd.to_numeric(bids_df['price'])
            bids_df['qty'] = pd.to_numeric(bids_df['qty'])
            asks_df['price'] = pd.to_numeric(asks_df['price'])
            asks_df['qty'] = pd.to_numeric(asks_df['qty'])

            asks_df = asks_df.iloc[::-1]  # 매도 호가 역순 정렬
            return bids_df.head(5), asks_df.head(5)  # 상위 5개만 표시
        else:
            st.error(f"API returned an error: {data.get('error_code', 'Unknown error')}")
    else:
        st.error(f"Failed to fetch data from API. Status code: {response.status_code}")
    return None, None

# 전체 잔고 조회 함수
def fetch_balances():
    action = '/v2.1/account/balance/all'
    payload = {'access_token': ACCESS_TOKEN}
    result = get_response(action, payload)

    if result:
        balances = result.get('balances', [])
        filtered_balances = {}
        for balance in balances:
            currency = balance.get('currency', '').lower()
            if currency in ['krw', 'usdt']:
                filtered_balances[currency] = {
                    'available': float(balance.get('available', '0')),
                    'limit': float(balance.get('limit', '0')),
                    'total': float(balance.get('available', '0')) + float(balance.get('limit', '0'))
                }
        return filtered_balances
    else:
        st.error("잔고 조회 오류 발생")
        return {}

# 매수/매도 주문 함수
def place_order(order_type, side, price, quantity):
    action = "/v2.1/order"
    order_uuid = str(uuid.uuid4())
    log_data = {
        "timestamp": datetime.now().isoformat(),
        "uuid": order_uuid,
        "order_type": "LIMIT",  # 항상 지정가로 설정
        "side": side,
        "price": price,
        "quantity": quantity,
        "status": "initiated"
    }

    try:
        payload = {
            "access_token": ACCESS_TOKEN,
            "nonce": order_uuid,
            "side": side,
            "quote_currency": "KRW",
            "target_currency": "USDT",
            "type": "LIMIT",  # 항상 지정가로 설정
            "price": f"{float(price):.2f}",
            "qty": f"{float(quantity):.4f}",
            "post_only": False  # 이 줄을 추가합니다
        }

        # 최소 주문 기준 설정
        MIN_ORDER_AMOUNT_KRW = 1000
        MIN_ORDER_QTY_USDT = 0.001

        price_value = float(price)
        quantity_value = float(quantity)

        if price_value <= 0 or quantity_value <= 0:
            raise ValueError("가격 및 수량은 0보다 커야 합니다.")
        
        if price_value * quantity_value < MIN_ORDER_AMOUNT_KRW:
            raise ValueError(f"주문 금액이 최소 금액 {MIN_ORDER_AMOUNT_KRW} KRW보다 작습니다.")

        if quantity_value < MIN_ORDER_QTY_USDT:
            raise ValueError(f"주문 수량이 최소 수량 {MIN_ORDER_QTY_USDT} USDT보다 작습니다.")

        result = get_response(action, payload)

        if result and result.get('result') == 'success':
            order_id = result.get('order_id')
            st.success(f"{side} 주문이 성공적으로 접수되었습니다. 주문 ID: {order_id}")
            log_data["status"] = "success"
            log_data["order_id"] = order_id
            log_data["response"] = result
            
            if 'order_tracking' not in st.session_state:
                st.session_state.order_tracking = {}
            st.session_state.order_tracking[order_uuid] = {
                'order_id': order_id,
                'status': 'pending',
                'side': side,
                'type': "LIMIT",
                'price': price,
                'quantity': quantity
            }
            
            st.session_state.orders = fetch_active_orders()
            st.rerun()
        else:
            st.error("주문 오류 발생")
            log_data["status"] = "api_error"
            log_data["error_message"] = "API 응답 실패"

    except ValueError as e:
        st.error(f"입력 오류: {e}")
        log_data["status"] = "input_error"
        log_data["error_message"] = str(e)
    except Exception as e:
        st.error(f"주문 처리 중 오류 발생: {e}")
        log_data["status"] = "processing_error"
        log_data["error_message"] = str(e)
    finally:
        save_log(log_data)

    return log_data["status"] == "success"


# 미체결 주문 조회 함수
def fetch_active_orders():
    action = "/v2.1/order/active_orders"
    payload = {
        "access_token": ACCESS_TOKEN,
        "nonce": str(uuid.uuid4()),
        "quote_currency": "KRW",
        "target_currency": "USDT"
    }

    result = get_response(action, payload)

    if result:
        return result.get('active_orders', [])
    else:
        st.error("미체결 주문 조회 오류 발생")
        return []

# 주문 취소 함수
def cancel_order(order_id):
    action = "/v2.1/order/cancel"
    payload = {
        "access_token": ACCESS_TOKEN,
        "nonce": str(uuid.uuid4()),
        "order_id": order_id,
        "quote_currency": "KRW",
        "target_currency": "USDT"
    }

    result = get_response(action, payload)

    if result:
        st.success(f"주문이 성공적으로 취소되었습니다. 주문 ID: {order_id}")
    else:
        st.error("주문 취소 오류 발생")

# 자동으로 잔고와 주문내역 업데이트 함수
def update_data():
    if st.session_state.get('last_update_time', 0) < time.time() - 0.5:
        st.session_state.balances = fetch_balances()
        st.session_state.orders = fetch_active_orders()
        st.session_state.orderbook = fetch_order_book()
        st.session_state.last_update_time = time.time()

# 잔고 정보 업데이트 및 표시 함수
def update_balance_info():
    balances = st.session_state.balances
    krw_balance = balances.get('krw', {})
    usdt_balance = balances.get('usdt', {})
    
    available_krw = float(krw_balance.get('available', '0'))
    limit_krw = float(krw_balance.get('limit', '0'))
    total_krw = available_krw + limit_krw
    
    available_usdt = float(usdt_balance.get('available', '0'))
    limit_usdt = float(usdt_balance.get('limit', '0'))
    total_usdt = available_usdt + limit_usdt

    st.markdown("""
    ### 계좌 잔고
    | 화폐 | 보유 | 주문 가능 |
    |:-----|-----:|----------:|
    | KRW  | {:,.0f} | {:,.0f} |
    | USDT | {:,.2f} | {:,.2f} |
    """.format(total_krw, available_krw, total_usdt, available_usdt))

# 초기 세션 상태 설정
if 'orderbook' not in st.session_state:
    st.session_state.orderbook = fetch_order_book()

# 업데이트 호출
update_data()

# 잔고 정보 표시
update_balance_info()

# 스타일 설정
st.markdown("""
<style>
    .reportview-container .main .block-container {
        padding-top: 1rem;
        padding-right: 1rem;
        padding-left: 1rem;
        padding-bottom: 1rem;
        max-width: 100%;
    }
    .stButton > button {
        width: 100%;
        padding: 0.1rem 0.1rem;
        font-size: 0.6rem;
        transition: all 0.3s ease;
        background-color: #4CAF50 !important;  /* 약간 옅은 초록색 배경 */
        color: white !important;  /* 흰색 글자 */
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        opacity: 0.9;  /* 호버 시 약간 투명해지는 효과 */
    }
    .stTextInput > div > div > input {
        font-size: 0.7rem;
    }
    .sidebar .sidebar-content {
        width: 200px;
    }
    .small-font {
        font-size: 0.7rem;
    }
    .stSelectbox {
        font-size: 0.7rem;
    }
    .stSlider {
        width: 180px;
    }
    
    .buy-button {
        background-color: #ff4b4b !important;
        color: white !important;
    }
    .sell-button {
        background-color: #4b4bff !important;  /* 파란색 배경 */
        color: white !important;  /* 흰색 글자 */
    }
    .ask-button {
        background-color: #ff4b4b !important;
        color: white !important;
        font-size: 0.6rem !important;
        padding: 2px 5px !important;
        margin: 2px 0 !important;
    }
    .ask-button:hover {
        opacity: 0.8;
    }
    .cancel-button {
        background-color: #ff9800 !important;
        color: white !important;
        font-size: 0.6rem !important;
        padding: 2px 5px !important;
    }
</style>
""", unsafe_allow_html=True)

# 메인 페이지 내용
# st.title("Coinone 매도 Tool", anchor=False)

# 주문 창
col_left, col_right = st.columns([1, 1])

with col_right:
    order_type_display = st.selectbox("주문 유형", ["지정가"], key='order_type')
    order_type = "LIMIT" if order_type_display == "지정가" else "MARKET" if order_type_display == "시장가" else "STOP_LIMIT"

    side_display = "매도"
    side = "SELL"

    if order_type != "MARKET":
        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown("<div style='font-size: 1.1em; margin-bottom: 0.5em;'>매도 호가</div>", unsafe_allow_html=True)
            bids_df, asks_df = st.session_state.orderbook
            if asks_df is not None:
                # 첫 번째와 두 번째 행을 건너뛰고 나머지 행을 표시
                for i, ask in asks_df.iloc[2:].iterrows():
                    if st.button(f"{ask['price']:,.0f}", key=f"ask_btn_{i}", help="클릭하여 가격 선택"):
                        st.session_state.selected_price = f"{ask['price']:,.0f}"
            
            st.markdown("<div style='font-size: 1.1em; margin-top: 1em; margin-bottom: 0.5em;'>매수 호가</div>", unsafe_allow_html=True)
            if asks_df is not None and len(asks_df) > 0:
                lowest_ask = asks_df['price'].min()
                for i in range(2):
                    price = lowest_ask - (i + 1)
                    if st.button(f"{price:,.0f}", key=f"bid_btn_{i}", help="클릭하여 가격 선택"):
                        st.session_state.selected_price = f"{price:,.0f}"
            
            # 호가 정보 업데이트 버튼 추가
            if st.button("호가 정보 업데이트", key="update_orderbook"):
                st.session_state.orderbook = fetch_order_book()
                st.success("호가 정보가 업데이트되었습니다.")

        with col2:
            price_display = st.text_input("가격 (KRW)", st.session_state.get('selected_price', ''), key='price')
            st.markdown('<style>div[data-testid="stTextInput"] > div > div > input { font-size: 1rem !important; }</style>', unsafe_allow_html=True)
            price = price_display.replace(',', '') if price_display else None
    else:
        price = None

    percentage = st.slider("매도 비율 (%)", min_value=0, max_value=100, value=0, step=1, key='percentage')

    # Calculate quantity based on percentage and price
    quantity = '0'
    krw_equivalent = 0  # KRW로 환산된 금액
    if percentage > 0:
        try:
            if order_type != "MARKET" and (price is None or price == ''):
                st.warning("가격을 입력해주세요.")
            else:
                price_value = float(price) if price else 0
                if price_value <= 0:
                    st.warning("가격은 0보다 커야 합니다.")
                else:
                    available_usdt = float(st.session_state.balances.get('usdt', {}).get('available', '0'))
                    if side == "BUY":
                        available_krw = float(st.session_state.balances.get('krw', {}).get('available', '0'))
                        amount_krw = available_krw * (percentage / 100)
                        quantity_value = amount_krw / price_value
                        quantity = f"{math.floor(quantity_value)}"  # 수량을 정수로 내림 처리
                        krw_equivalent = amount_krw
                    else:
                        amount_usdt = available_usdt * (percentage / 100)
                        # 0단위 내림 처리
                        quantity_value = math.floor(amount_usdt)
                        quantity = f"{quantity_value}"  # 수량을 정수로 포맷
                        krw_equivalent = quantity_value * price_value
        except ValueError:
            st.warning("유효한 가격을 입력해주세요.")
        
        st.markdown("<div class='small-font'>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            quantity_input = st.text_input("수량 (USDT)", value=quantity, disabled=True)
        with col2:
            st.write(f"환산 금액: {krw_equivalent:,.0f} KRW")
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        quantity = st.text_input("수량 (USDT)", value="0")




    if st.button(f"{side_display} 주문하기", key="place_order", help="클릭하여 주문 실행"):
        place_order(order_type, side, price, quantity)

    st.markdown("</div>", unsafe_allow_html=True)

    # 미체결 주문 관련 기능 추가
    st.markdown("### 매도 미체결 주문")
    orders = fetch_active_orders()
    sell_orders = [order for order in orders if order['side'] == 'SELL']
    
    if sell_orders:
        for order in sell_orders:
            col1, col2, col3, col4, col5 = st.columns(5)
            col1.write(f"종목: {order['target_currency']}")
            col2.write(f"유형: {order['type']}")
            col3.write(f"가격: {float(order['price']):,.2f}")
            col4.write(f"수량: {float(order['remain_qty']):,.4f}")
            if col5.button(f"취소", key=f"cancel_{order['order_id']}", help="클릭하여 주문 취소"):
                cancel_order(order['order_id'])
                st.rerun()
    else:
        st.info("매도 미체결 주문 없음")

    # UUID 조회 기능 추가
    st.markdown("### 주문 조회")
    order_id_input = st.text_input("주문 ID 입력", key="order_id_input")
    if st.button("주문 조회", key="fetch_order_detail"):
        if order_id_input:
            order_detail = fetch_order_detail(order_id_input)
            if order_detail:
                st.write("주문 정보:")
                st.markdown(f"""
                <div style="font-size: 70%;">
                주문 ID: {order_detail['order_id']}<br><br>
                주문 유형: {order_detail['type']}<br><br>
                거래 화폐: {order_detail['quote_currency']}/{order_detail['target_currency']}<br><br>
                상태: {order_detail['status']}<br><br>
                매수/매도: {order_detail['side']}<br><br>
                주문 가격: {order_detail['price']} {order_detail['quote_currency']}<br><br>
                주문 수량: {order_detail['original_qty']} {order_detail['target_currency']}<br><br>
                체결된 수량: {order_detail['executed_qty']} {order_detail['target_currency']}<br><br>
                남은 수량: {order_detail['remain_qty']} {order_detail['target_currency']}<br><br>
                주문 시간: {datetime.fromtimestamp(int(order_detail['ordered_at'])/1000).strftime('%Y-%m-%d %H:%M:%S')}<br><br>
                마지막 업데이트: {datetime.fromtimestamp(int(order_detail['updated_at'])/1000).strftime('%Y-%m-%d %H:%M:%S')}
                </div>
                """, unsafe_allow_html=True)
            else:
                st.warning("해당 주문 ID로 주문을 찾을 수 없습니다.")
        else:
            st.warning("주문 ID를 입력해주세요.")


    # 최근 주문 정보 표시
    st.markdown("### 최근 주문 내역")
    try:
        with open('order_log.json', 'r') as f:
            logs = json.load(f)
        
        # 주문 시간을 기준으로 내림차순 정렬
        sorted_logs = sorted(logs, key=lambda x: x['timestamp'], reverse=True)
        
        # 최대 20개까지 표시
        for log in sorted_logs[:20]:
            # 타임스탬프를 datetime 객체로 변환
            timestamp = datetime.fromisoformat(log['timestamp'])
            # UTC 시간을 태국 시간으로 변환 (UTC+7)
            thailand_time = timestamp + timedelta(hours=7)
            # 초 단위까지만 포맷팅
            formatted_time = thailand_time.strftime("%Y-%m-%d %H:%M:%S")
            st.write(f"주문 시간(태국): {formatted_time}")
            order_id = log.get('order_id')
            if order_id is None or order_id == "null":
                # response 내부의 market_order에서 order_id 찾기
                response = log.get('response', {})
                market_order = response.get('market_order', {})
                order_id = market_order.get('order_id', '주문 ID 없음')
            
            st.write(f"{order_id}")
            st.write("---")  # 각 주문 사이에 구분선 추가
    except FileNotFoundError:
        st.info("주문 로그가 없습니다.")
    except json.JSONDecodeError:
        st.error("주문 로그 파일을 읽는 중 오류가 발생했습니다.")
    

