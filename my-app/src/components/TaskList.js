import React, { useState, useEffect } from 'react';
import './TaskList.css';

function TaskList() {
  const [tasks, setTasks] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchTasks = async () => {
      try {
        const response = await fetch('http://localhost:5000/api/tasks');
        if (!response.ok) {
          throw new Error('获取任务列表失败');
        }
        const data = await response.json();
        setTasks(data);
        setError(null);
      } catch (err) {
        setError(err.message);
      } finally {
        setIsLoading(false);
      }
    };

    fetchTasks();
    const interval = setInterval(fetchTasks, 3000); // 每3秒更新一次

    return () => clearInterval(interval);
  }, []);

  const getStatusText = (status) => {
    const statusMap = {
      'pending': '等待中',
      'running': '进行中',
      'completed': '已完成',
      'failed': '失败'
    };
    return statusMap[status] || status;
  };

  const getStatusClass = (status) => {
    return `status-badge ${status}`;
  };

  if (isLoading) {
    return <div className="loading">加载中...</div>;
  }

  if (error) {
    return <div className="error">错误: {error}</div>;
  }

  return (
    <div className="task-list">
      <h2>采集任务列表</h2>
      {tasks.length === 0 ? (
        <p className="no-tasks">暂无任务</p>
      ) : (
        <div className="task-grid">
          {tasks.map(task => (
            <div key={task.task_id} className="task-card">
              <div className="task-header">
                <h3>{task.query}</h3>
                <span className={getStatusClass(task.status)}>
                  {getStatusText(task.status)}
                </span>
              </div>
              
              <div className="task-info">
                <p>类型: {
                  task.task_type === 'keyword' ? '关键词搜索' :
                  task.task_type === 'user' ? '用户数据' : '版块数据'
                }</p>
                <p>目标数量: {task.target_count}</p>
                <p>已采集: {task.current_count || 0}</p>
              </div>

              <div className="progress-container">
                <div 
                  className="progress-bar"
                  style={{width: `${task.progress || 0}%`}}
                ></div>
                <span className="progress-text">
                  {Math.round(task.progress || 0)}%
                </span>
              </div>

              <div className="task-footer">
                <p>创建时间: {new Date(task.created_at).toLocaleString()}</p>
                {task.completed_at && (
                  <p>完成时间: {new Date(task.completed_at).toLocaleString()}</p>
                )}
                {task.error_message && (
                  <p className="error-message">错误: {task.error_message}</p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default TaskList; 