import re
import json
from typing import List, Tuple, Optional

class RAGEngine:
    """Поиск по датасету на основе ключевых слов"""
    
    @staticmethod
    def extract_keywords(text: str) -> List[str]:
        """Извлекаем ключевые слова из текста"""
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        
        stop_words = {'и', 'в', 'не', 'что', 'он', 'на', 'я', 'с', 'как', 'а', 'то', 
                     'она', 'но', 'да', 'ты', 'к', 'у', 'же', 'вы', 'за', 'бы', 'по',
                     'мне', 'было', 'от', 'меня', 'нет', 'о', 'из', 'ему', 'когда',
                     'даже', 'ну', 'ли', 'уже', 'или', 'быть', 'был', 'до', 'вас',
                     'сказал', 'там', 'потом', 'себя', 'ей', 'может', 'они', 'тут',
                     'где', 'есть', 'надо', 'для', 'мы', 'их', 'чем', 'была', 'сам',
                     'чтоб', 'без', 'будто', 'чего', 'раз', 'тоже', 'себе', 'под',
                     'жизнь', 'будет', 'тогда', 'кто', 'этот', 'говорил', 'того',
                     'потому', 'этого', 'какой', 'совсем', 'ним', 'здесь', 'этом',
                     'один', 'почти', 'мой', 'тем', 'чтобы', 'нее', 'кажется',
                     'сейчас', 'были', 'куда', 'зачем', 'сказать', 'всех', 'никогда',
                     'сегодня', 'можно', 'при', 'наконец', 'два', 'об', 'другой',
                     'хоть', 'после', 'над', 'больше', 'тот', 'через', 'эти', 'нас',
                     'про', 'всего', 'них', 'какая', 'много', 'разве', 'сказала',
                     'три', 'эту', 'моя', 'перед', 'иногда', 'лучше', 'чуть', 'том',
                     'нельзя', 'такой', 'им', 'более', 'всегда', 'конечно', 'всю',
                     'между'}
        
        words = text.split()
        keywords = [word for word in words if len(word) > 2 and word not in stop_words]
        return keywords
    
    @staticmethod
    def parse_dataset_file(file_path: str) -> List[Tuple[str, str, str]]:
        """
        Парсим файл с датасетом
        Поддерживаемые форматы: JSON и TXT
        """
        pairs = []
        
        try:
            if file_path.endswith('.json'):
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and 'question' in item and 'answer' in item:
                                q = str(item['question']).strip()
                                a = str(item['answer']).strip()
                                if q and a:
                                    keywords = ' '.join(RAGEngine.extract_keywords(q))
                                    pairs.append((q, a, keywords))
                    elif isinstance(data, dict):
                        for q, a in data.items():
                            q = str(q).strip()
                            a = str(a).strip()
                            if q and a:
                                keywords = ' '.join(RAGEngine.extract_keywords(q))
                                pairs.append((q, a, keywords))
            
            elif file_path.endswith('.txt'):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                blocks = re.split(r'\n\s*\n|\n={3,}\n', content.strip())
                
                for block in blocks:
                    lines = [l.strip() for l in block.strip().split('\n') if l.strip()]
                    if len(lines) >= 2:
                        question = lines[0]
                        answer = '\n'.join(lines[1:])
                        keywords = ' '.join(RAGEngine.extract_keywords(question))
                        pairs.append((question, answer, keywords))
        
        except Exception as e:
            print(f"Ошибка парсинга файла {file_path}: {e}")
        
        return pairs
    
    @staticmethod
    def find_best_answer(user_message: str, qa_pairs: List[Tuple[str, str, str]]) -> Optional[str]:
        """
        Находим лучший ответ на основе совпадения ключевых слов
        """
        if not qa_pairs:
            return None
        
        user_keywords = set(RAGEngine.extract_keywords(user_message))
        if not user_keywords:
            return None
        
        best_score = 0
        best_answer = None
        
        for question, answer, keywords_str in qa_pairs:
            keywords = set(keywords_str.split())
            common = user_keywords & keywords
            score = len(common)
            
            if score > best_score:
                best_score = score
                best_answer = answer
        
        if best_score >= 1:
            return best_answer
        
        return None
    
    @staticmethod
    def get_stats(qa_pairs: List[Tuple[str, str, str]]) -> str:
        """Статистика датасета"""
        total = len(qa_pairs)
        if total == 0:
            return "Датасет пуст"
        
        avg_q_len = sum(len(q) for q, _, _ in qa_pairs) / total
        avg_a_len = sum(len(a) for _, a, _ in qa_pairs) / total
        
        return f"Записей: {total} | Ср. длина вопроса: {avg_q_len:.0f} | Ср. длина ответа: {avg_a_len:.0f}"
