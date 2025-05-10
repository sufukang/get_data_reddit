import praw
import pymongo
from datetime import datetime
from pymongo import MongoClient
import random
import time
from typing import List, Dict
from flask import Flask, request, jsonify
from flask_cors import CORS
import threading
from bson import ObjectId
import logging

app = Flask(__name__)
CORS(app)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler('reddit_scraper.log'),
        logging.StreamHandler()
    ]
)

# Reddit 账号池配置
REDDIT_ACCOUNTS = [
    {
        "client_id": "cU5aXYM2mg0sWOq8SyV0fw",
        "client_secret": "xHfOJvR84yWemZl2HKCy1sHJAUeTJw",
        "user_agent": "Middle_Breakfast8592"
    },
    # 添加更多账号
    {
        "client_id": "Gx7nSI8Vlv02716EnBR2WA",
        "client_secret": "6R3jkaRkGsP7vGuV5wlY1ZYm77FzMQ",
        "user_agent": "KKConstantine"
    },

    {
        "client_id": "GEKZlOPcIIw27DvftU85Xg",
        "client_secret": "Oz44IWDUSZk6bRhkSuJM3xzv1Cbnug",
        "user_agent": "Ambitious-Cup8681"
    }
]

class RedditTask:
    def __init__(self, query: str):
        self.task_id = str(ObjectId())
        self.status = "pending"
        self.progress = 0
        self.target_count = 0
        self.current_count = 0
        self.task_type = ""  # keyword, user, subreddit
        self.query = query
        self.created_at = datetime.utcnow()
        self.completed_at = None
        self.error_message = None
        # 使用查询内容创建集合名
        self.collection_name = f"reddit_posts_{query.lower()}"  # 转换为小写以保持一致性

class RedditScraper:
    def __init__(self):
        try:
            # MongoDB 连接配置
            self.client = MongoClient('mongodb://localhost:27017/', 
                                    serverSelectionTimeoutMS=5000)
            self.client.server_info()
            
            self.db = self.client['reddit_db']
            self.tasks_collection = self.db['reddit_tasks']
            
            # 初始化 Reddit 客户端池
            self.reddit_clients = self._initialize_reddit_clients()
            self.active_tasks = {}
            self.total_scraped = 0
            
            # 配置参数
            self.min_delay = 0.5
            self.max_delay = 1.0
            self.error_delay = 10
            self.batch_size = 100
            self.max_target_count = 100000  # 最大抓取数量限制
            
            logging.info("成功连接到 MongoDB")
            
        except Exception as e:
            logging.error(f"MongoDB 连接失败: {str(e)}")
            raise Exception("无法连接到数据库，请确保 MongoDB 服务已启动")

    def _initialize_reddit_clients(self) -> List[praw.Reddit]:
        """初始化所有 Reddit 客户端"""
        clients = []
        for account in REDDIT_ACCOUNTS:
            client = praw.Reddit(
                client_id=account['client_id'],
                client_secret=account['client_secret'],
                user_agent=account['user_agent']
            )
            clients.append(client)
        return clients
    
    def _get_random_client(self) -> praw.Reddit:
        """随机获取一个 Reddit 客户端"""
        return random.choice(self.reddit_clients)
    
    def _add_delay(self):
        """添加较短的随机延迟"""
        delay = random.uniform(self.min_delay, self.max_delay)
        time.sleep(delay)
    
    def _run_task(self, task_id: str):
        """运行抓取任务"""
        task = self.tasks_collection.find_one({"task_id": task_id})
        
        try:
            self.tasks_collection.update_one(
                {"task_id": task_id},
                {"$set": {"status": "running"}}
            )
            
            if task["task_type"] == "keyword":
                self._scrape_by_keyword(task)
            elif task["task_type"] == "user":
                self._scrape_by_user(task)
            elif task["task_type"] == "subreddit":
                self._scrape_by_subreddit(task)
                
            self.tasks_collection.update_one(
                {"task_id": task_id},
                {
                    "$set": {
                        "status": "completed",
                        "completed_at": datetime.utcnow()
                    }
                }
            )
            
        except Exception as e:
            self.tasks_collection.update_one(
                {"task_id": task_id},
                {
                    "$set": {
                        "status": "failed",
                        "error_message": str(e)
                    }
                }
            )

    def _update_progress(self, task_id: str, current_count: int):
        """更新任务进度"""
        task = self.tasks_collection.find_one({"task_id": task_id})
        progress = (current_count / task["target_count"]) * 100
        
        self.tasks_collection.update_one(
            {"task_id": task_id},
            {
                "$set": {
                    "current_count": current_count,
                    "progress": progress
                }
            }
        )

    def _scrape_by_keyword(self, task: dict):
        """优化的关键词搜索方法"""
        reddit = self._get_random_client()
        posts_scraped = 0
        retries = 3
        
        while posts_scraped < task["target_count"]:
            try:
                remaining = task["target_count"] - posts_scraped
                # 使用更大的批次大小
                for submission in reddit.subreddit("all").search(
                    task["query"],
                    sort='relevance',
                    limit=min(self.batch_size * 2, remaining),
                    time_filter='all'
                ):
                    if self._save_post(submission, task, "keyword"):
                        posts_scraped += 1
                        self._update_progress(task["task_id"], posts_scraped)
                        if posts_scraped >= task["target_count"]:
                            break
                    self._add_delay()
                    
            except Exception as e:
                print(f"Error: {str(e)}")
                retries -= 1
                if retries <= 0:
                    break
                time.sleep(self.error_delay)

    def _scrape_by_user(self, task: dict):
        """优化的用户数据抓取方法"""
        reddit = self._get_random_client()
        posts_scraped = 0
        retries = 3
        
        try:
            user = reddit.redditor(task["query"])
            # 同时获取用户的帖子和评论
            submissions = user.submissions.new(limit=None)
            
            for submission in submissions:
                if posts_scraped >= task["target_count"]:
                    break
                if self._save_post(submission, task, "user"):
                    posts_scraped += 1
                    self._update_progress(task["task_id"], posts_scraped)
                self._add_delay()
                
        except Exception as e:
            print(f"Error: {str(e)}")
            if retries > 0:
                retries -= 1
                time.sleep(self.error_delay)

    def _scrape_by_subreddit(self, task: dict):
        """优化的subreddit抓取方法，优先获取最新帖子"""
        posts_scraped = 0
        retries = 3
        
        while posts_scraped < task["target_count"]:
            try:
                reddit = self._get_random_client()
                subreddit = reddit.subreddit(task["query"])
                
                # 主要使用 new 排序来获取最新帖子
                try:
                    # 首先获取最新的帖子
                    posts = list(subreddit.new(limit=min(100, task["target_count"] - posts_scraped)))
                    
                    if not posts:
                        # 如果没有获取到新帖子，尝试其他排序方式
                        for sort_method in ['hot', 'top']:
                            if posts_scraped >= task["target_count"]:
                                break
                                
                            if sort_method == 'top':
                                # 对于 top 帖子，优先获取最近时间的
                                time_filters = ['hour', 'day', 'week', 'month', 'year', 'all']
                                for time_filter in time_filters:
                                    if posts_scraped >= task["target_count"]:
                                        break
                                    try:
                                        posts = list(subreddit.top(
                                            time_filter=time_filter,
                                            limit=min(100, task["target_count"] - posts_scraped)
                                        ))
                                        # 按发布时间排序
                                        posts.sort(key=lambda x: x.created_utc, reverse=True)
                                        
                                        for post in posts:
                                            if self._save_post(post, task, "subreddit"):
                                                posts_scraped += 1
                                                self._update_progress(task["task_id"], posts_scraped)
                                                if posts_scraped >= task["target_count"]:
                                                    break
                                            self._add_delay()
                                    except Exception as e:
                                        logging.error(f"Error in top {time_filter}: {str(e)}")
                                        continue
                            else:
                                try:
                                    posts = list(getattr(subreddit, sort_method)(
                                        limit=min(100, task["target_count"] - posts_scraped)
                                    ))
                                    # 按发布时间排序
                                    posts.sort(key=lambda x: x.created_utc, reverse=True)
                                    
                                    for post in posts:
                                        if self._save_post(post, task, "subreddit"):
                                            posts_scraped += 1
                                            self._update_progress(task["task_id"], posts_scraped)
                                            if posts_scraped >= task["target_count"]:
                                                break
                                        self._add_delay()
                                except Exception as e:
                                    logging.error(f"Error in {sort_method}: {str(e)}")
                                    continue
                    else:
                        # 处理最新的帖子
                        for post in posts:
                            if self._save_post(post, task, "subreddit"):
                                posts_scraped += 1
                                self._update_progress(task["task_id"], posts_scraped)
                                if posts_scraped >= task["target_count"]:
                                    break
                            self._add_delay()
                            
                except Exception as e:
                    logging.error(f"Error in new posts: {str(e)}")
                    time.sleep(5)
                    continue
                    
            except Exception as e:
                logging.error(f"Error in {task['query']}: {str(e)}")
                retries -= 1
                if retries <= 0:
                    break
                time.sleep(self.error_delay)

    def _save_post(self, post, task: dict, source_type: str) -> bool:
        """保存帖子到数据库和单个文件，按时间排序"""
        try:
            # 准备帖子数据
            post_data = {
                'author': str(post.author),
                'title': post.title,
                'score': post.score,
                'url': post.url,
                'created_utc': datetime.fromtimestamp(post.created_utc),
                'post_id': post.id,
                'permalink': post.permalink,
                'num_comments': post.num_comments,
                'source_type': source_type,
                'query': task["query"],
                'scraped_at': datetime.utcnow(),
                'selftext': post.selftext if hasattr(post, 'selftext') else '',
                'subreddit': str(post.subreddit)
            }
            
            # 保存到MongoDB
            collection = self.db[task["collection_name"]]
            
            # 创建时间索引（如果不存在）
            if 'created_utc_1' not in collection.index_information():
                collection.create_index([('created_utc', pymongo.DESCENDING)])
            
            result = collection.update_one(
                {'post_id': post.id},
                {'$set': post_data},
                upsert=True
            )
            
            # 保存到单个data.txt文件，最新的在前面
            if result.upserted_id or result.modified_count > 0:
                self.total_scraped += 1
                
                with open('data.txt', 'a', encoding='utf-8') as f:
                    f.write(f"\n{'='*50}\n")
                    f.write(f"Task: {task['query']} ({source_type})\n")
                    f.write(f"Created Time: {post_data['created_utc']}\n")  # 显示创建时间
                    f.write(f"Title: {post_data['title']}\n")
                    f.write(f"Author: {post_data['author']}\n")
                    f.write(f"Score: {post_data['score']}\n")
                    f.write(f"Comments: {post_data['num_comments']}\n")
                    f.write(f"URL: {post_data['url']}\n")
                    f.write(f"Subreddit: {post_data['subreddit']}\n")
                    if post_data['selftext']:
                        f.write(f"Content:\n{post_data['selftext']}\n")
                    f.write(f"Scraped: {post_data['scraped_at']}\n")
                
                if self.total_scraped % 100 == 0:
                    logging.info(f"已采集数据: {self.total_scraped} - 当前任务({task['query']}): {task.get('current_count', 0)}/{task['target_count']}")
            return True
            
        except Exception as e:
            logging.error(f"保存帖子时出错: {str(e)}")
            return False

    def create_task(self, task_type: str, query: str, target_count: int) -> str:
        """创建新的抓取任务"""
        try:
            # 验证目标数量
            if target_count > self.max_target_count:
                raise ValueError(f"目标数量不能超过 {self.max_target_count} 条")
            
            task = RedditTask(query)
            task.task_type = task_type
            task.target_count = target_count
            
            # 为大量数据创建分块索引
            if task.collection_name not in self.db.list_collection_names():
                self.db.create_collection(task.collection_name)
                self.db[task.collection_name].create_index([
                    ('post_id', pymongo.ASCENDING)
                ], unique=True)
                self.db[task.collection_name].create_index([
                    ('created_utc', pymongo.DESCENDING)
                ])
                self.db[task.collection_name].create_index([
                    ('score', pymongo.DESCENDING)
                ])
            
            # 保存任务信息
            task_dict = task.__dict__
            self.tasks_collection.insert_one(task_dict)
            
            # 启动异步任务
            thread = threading.Thread(
                target=self._run_task,
                args=(task.task_id,)
            )
            thread.start()
            
            return task.task_id
            
        except Exception as e:
            error_msg = f"创建任务失败: {str(e)}"
            logging.error(error_msg)
            raise Exception(error_msg)

# 初始化全局爬虫实例
scraper = RedditScraper()

@app.route('/api/tasks', methods=['POST'])
def create_task():
    try:
        data = request.json
        query = data['query'].strip()
        target_count = int(data['target_count'])
        
        if not query:
            return jsonify({"error": "查询内容不能为空"}), 400
            
        if any(char in query for char in ['/', '\\', ' ', '.', '$']):
            return jsonify({"error": "查询内容不能包含特殊字符"}), 400
        
        if target_count <= 0:
            return jsonify({"error": "目标数量必须大于0"}), 400
            
        task_id = scraper.create_task(
            data['task_type'],
            query,
            target_count
        )
        
        return jsonify({
            "task_id": task_id,
            "collection_name": f"reddit_posts_{query.lower()}"
        })
        
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logging.error(f"创建任务时出错: {str(e)}")
        return jsonify({"error": "创建任务失败，请检查服务器日志"}), 500

@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    tasks = list(scraper.tasks_collection.find(
        {},
        {'_id': 0}
    ))
    return jsonify(tasks)

@app.route('/api/tasks/<task_id>', methods=['GET'])
def get_task(task_id):
    task = scraper.tasks_collection.find_one(
        {"task_id": task_id},
        {'_id': 0}
    )
    return jsonify(task)

@app.route('/api/tasks/<task_id>/data', methods=['GET'])
def get_task_data(task_id):
    """获取特定任务的数据"""
    try:
        # 先获取任务信息
        task = scraper.tasks_collection.find_one({"task_id": task_id})
        if not task:
            return jsonify({"error": "任务不存在"}), 404
            
        # 使用任务中的query获取对应集合的数据
        collection_name = f"reddit_posts_{task['query'].lower()}"
        posts = list(scraper.db[collection_name].find({}, {'_id': 0}))
        return jsonify(posts)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.after_request
def after_request(response):
    """每个请求后的处理"""
    if response.status_code == 200:
        logging.info(f"请求成功 - 总采集数据: {scraper.total_scraped}")
    return response

if __name__ == '__main__':
    app.run(port=5000)


