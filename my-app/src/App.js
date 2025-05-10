import React from 'react';
import { BrowserRouter as Router, Route, Routes, Link } from 'react-router-dom';
import TaskCreation from './components/TaskCreation';
import TaskList from './components/TaskList';
import './App.css';

function App() {
  return (
    <Router>
      <div className="App">
        <nav className="navbar">
          <div className="nav-container">
            <h1>Reddit 数据采集系统</h1>
            <ul>
              <li><Link to="/create">新建任务</Link></li>
              <li><Link to="/tasks">任务列表</Link></li>
            </ul>
          </div>
        </nav>

        <div className="container">
          <Routes>
            <Route path="/create" element={<TaskCreation />} />
            <Route path="/tasks" element={<TaskList />} />
            <Route path="/" element={<TaskCreation />} />
          </Routes>
        </div>
      </div>
    </Router>
  );
}

export default App; 