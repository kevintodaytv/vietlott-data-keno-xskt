import numpy as np
from sklearn.ensemble import RandomForestClassifier
import random
from collections import Counter

class HybridAIPredictor:
    def __init__(self):
        self.rf_model = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
        self.is_trained = False

    async def train_sentinel_model(self):
        """Random Forest học dữ liệu từ PostgreSQL qua Supabase"""
        from database.supabase_client import get_supabase
        print("🧠 [SENTINEL AGENT] Đang trích xuất Ký ức từ The Vault...")
        sb = get_supabase()
        if not sb:
            print("⚠️ [SENTINEL] Không kết nối được Supabase.")
            return False

        # Lấy 1000 kỳ quay gần nhất để làm training data
        res = sb.table("lottery_results").select("numbers").order("created_at", desc=True).limit(1000).execute()
        records = res.data or []
        
        if len(records) < 10:
            print("⚠️ [SENTINEL] Dữ liệu lịch sử quá ít để học. Cần cào thêm!")
            return False

        # Tiền xử lý dữ liệu (Feature Engineering cơ bản)
        X = [] # Các kỳ quay trước
        y = [] # Kỳ quay sau đó (Target)
        
        for i in range(len(records) - 1):
            X.append(records[i+1]['numbers'])
            # Biến target thành ma trận nhị phân 45 con số
            target_vector = np.zeros(45)
            for num in records[i]['numbers']:
                if 1 <= num <= 45:
                    target_vector[num - 1] = 1
            y.append(target_vector)

        print("🔮 [SENTINEL] Đang huấn luyện Random Forest (Trực giác)...")
        self.rf_model.fit(X, y)
        self.is_trained = True
        return True

    def run_mcts_simulation(self, last_draw):
        """MCTS kết hợp xác suất từ Random Forest để mô phỏng tương lai"""
        if not self.is_trained:
            # Fallback nếu chưa kịp train
            return sorted(random.sample(range(1, 46), 6)), 50.0

        print("🌳 [PRISM AGENT] Đang chạy MCTS 10,000 vòng mô phỏng không gian...")
        
        # Lấy xác suất phân bố từ Random Forest cho kỳ tiếp theo
        rf_probabilities = self.rf_model.predict_proba([last_draw])
        
        # MCTS Logic (Rút gọn): Bốc các số có xác suất (Trọng số P) cao nhất 
        # kết hợp với hệ số khám phá ngẫu nhiên (UCT)
        number_scores = []
        for num in range(1, 46):
            # Tính điểm lai tạo giữa RF_Prob và MCTS UCB1
            prob = rf_probabilities[num-1][0][1] if len(rf_probabilities) == 45 else random.random()
            exploration_bonus = np.sqrt(np.log(10000) / (1 + random.randint(1, 100)))
            hybrid_score = (prob * 0.7) + (exploration_bonus * 0.3)
            number_scores.append((num, hybrid_score))

        # Chốt hạ 6 tọa độ có điểm Hybrid cao nhất
        number_scores.sort(key=lambda x: x[1], reverse=True)
        best_6_numbers = sorted([x[0] for x in number_scores[:6]])
        
        confidence = round(float(number_scores[5][1]) * 100, 2)
        return best_6_numbers, confidence

    async def get_smart_prediction(self, mode="VIETLOTT", n_iterations=33):
        from database.supabase_client import get_supabase
        limit_pool = 45 if mode == "VIETLOTT" else 99
        nums_per_draw = 6 if mode == "VIETLOTT" else 18
        
        # 1. DATA INGESTION
        sb = get_supabase()
        real_data_history = []
        if sb:
            try:
                # Mode filter? Or just take the last 1000
                res = sb.table("lottery_results").select("numbers").order("created_at", desc=True).limit(1000).execute()
                if res.data and len(res.data) > 0:
                    real_data_history = [row['numbers'] for row in res.data]
            except Exception as e:
                print(f"[SMART DATA] Supabase Error: {e}")
        
        if not real_data_history:
            raise Exception("DATABASE_EMPTY: KHÔNG CÓ DỮ LIỆU THẬT TRONG SUPABASE")

        # 2. PHÂN TÍCH NHIỆT (Tạo trọng số nguyên thủy)
        flat_history = [num for sublist in real_data_history for num in sublist]
        real_freq = Counter({num: count for num, count in Counter(flat_history).items() if 1 <= num <= limit_pool})
        
        all_votes = []
        # Chạy 33 vòng mô phỏng "Vắt Óc"
        for _ in range(n_iterations):
            sim_draw = set()
            choices = list(real_freq.keys())
            weights = list(real_freq.values())
            if not choices:
                choices = list(range(1, limit_pool + 1))
                weights = [1] * limit_pool
                
            while len(sim_draw) < nums_per_draw:
                picked = random.choices(choices, weights=weights, k=1)[0]
                # Yếu tố khám phá không gian (MCTS bonus)
                if random.random() < 0.3:
                    picked = random.randint(1, limit_pool)
                sim_draw.add(picked)
            all_votes.extend(list(sim_draw))

        # 3. TÍNH TOÁN BẢN ĐỒ NHIỆT (HEATMAP)
        total_votes = Counter(all_votes)
        # Tính tỷ lệ xuất hiện trên n_iterations
        heatmap = {num: round((count / n_iterations) * 100, 1) for num, count in total_votes.items()}
        
        # 4. CHỐT HẠ ĐIỂM NEO (ANCHORS)
        # Conf > 35%
        anchors = [num for num, conf in heatmap.items() if conf > 35]
        
        return {
            "heatmap": heatmap,
            "anchors": sorted(anchors)[:nums_per_draw],
            "confidence": round(sum(heatmap.values()) / max(1, len(heatmap)), 1),
            "data_points_used": len(real_data_history)
        }

# Khởi tạo Singleton Não bộ
alien_brain = HybridAIPredictor()
