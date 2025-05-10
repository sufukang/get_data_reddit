import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './TaskCreation.css';

function TaskCreation() {
  const [taskType, setTaskType] = useState('keyword');
  const [query, setQuery] = useState('');
  const [targetCount, setTargetCount] = useState(500);
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    
    try {
      const response = await fetch('http://localhost:5000/api/tasks', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          task_type: taskType,
          query: query,
          target_count: targetCount
        })
      });

      if (response.ok) {
        navigate('/tasks');
      } else {
        alert('创建任务失败，请重试');
      }
    } catch (error) {
      console.error('Error:', error);
      alert('创建任务失败，请检查服务器连接');
    } finally {
      setIsLoading(false);
    }
  };

  const getPlaceholder = () => {
    switch (taskType) {
      case 'keyword':
        return '请输入搜索关键词';
      case 'user':
        return '请输入Reddit用户名';
      case 'subreddit':
        return '请输入Subreddit名称';
      default:
        return '';
    }
  };

  return (
    <div className="task-creation">
      <h2>创建新采集任务</h2>
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label>采集类型：</label>
          <select 
            value={taskType} 
            onChange={(e) => setTaskType(e.target.value)}
            disabled={isLoading}
          >
            <option value="keyword">关键词搜索</option>
            <option value="user">用户数据</option>
            <option value="subreddit">版块数据</option>
          </select>
        </div>
        
        <div className="form-group">
          <label>查询内容：</label>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={getPlaceholder()}
            disabled={isLoading}
            required
          />
        </div>
        
        <div className="form-group">
          <label>目标数量：</label>
          <input
            type="number"
            value={targetCount}
            onChange={(e) => setTargetCount(parseInt(e.target.value))}
            min="1"
            max="100000"
            disabled={isLoading}
            required
          />
          <small className="form-text">
            可设置1-100,000条数据
          </small>
        </div>
        
        <button type="submit" disabled={isLoading}>
          {isLoading ? '创建中...' : '创建任务'}
        </button>
      </form>
    </div>
  );
}

export default TaskCreation; 