import React, { useState } from 'react';
import { Upload, Button, Card, Progress, message, Radio, Input } from 'antd';
import { InboxOutlined, FileTextOutlined } from '@ant-design/icons';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import './App.css';

const { Dragger } = Upload;
const { TextArea } = Input;

const API_BASE = 'http://localhost:8002';

function App() {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState('');
  const [taskId, setTaskId] = useState('');
  const [promptType, setPromptType] = useState('free');
  const [customPrompt, setCustomPrompt] = useState('');

  const prompts = {
    free: '<image>\\nFree OCR.',
    markdown: '<image>\\n<|grounding|>Convert the document to markdown.',
    table: '<image>\\n<|grounding|>OCR this image.',
    figure: '<image>\\nParse the figure.'
  };

  const uploadProps = {
    name: 'file',
    multiple: false,
    accept: '.pdf,.png,.jpg,.jpeg',
    beforeUpload: (file) => {
      setFile(file);
      return false;
    },
    onRemove: () => {
      setFile(null);
    }
  };

  const handleUpload = async () => {
    if (\!file) {
      message.error('请先选择文件');
      return;
    }

    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post(`${API_BASE}/api/upload`, formData);
      if (response.data.status === 'success') {
        message.success('文件上传成功');
        handleOCR(response.data.file_path, response.data.file_type);
      } else {
        message.error(response.data.message);
      }
    } catch (error) {
      message.error('上传失败: ' + error.message);
    } finally {
      setUploading(false);
    }
  };

  const handleOCR = async (filePath, fileType) => {
    setProcessing(true);
    setProgress(0);
    setResult('');

    const prompt = promptType === 'custom' ? customPrompt : prompts[promptType];

    try {
      const response = await axios.post(`${API_BASE}/api/ocr`, {
        file_path: filePath,
        file_type: fileType,
        prompt: prompt
      });

      if (response.data.status === 'running') {
        const tid = response.data.task_id;
        setTaskId(tid);
        
        // WebSocket 连接
        const ws = new WebSocket(`ws://localhost:8002/ws/${tid}`);
        
        ws.onmessage = async (event) => {
          const data = JSON.parse(event.data);
          
          if (data.progress \!== undefined) {
            setProgress(data.progress);
          }
          
          if (data.status === 'finished') {
            // 获取结果
            const resultResponse = await axios.get(`${API_BASE}/api/result/${tid}`);
            if (resultResponse.data.status === 'success') {
              setResult(resultResponse.data.content);
              message.success('OCR 识别完成\!');
            }
            setProcessing(false);
            ws.close();
          } else if (data.status === 'error') {
            message.error('OCR 识别失败: ' + data.message);
            setProcessing(false);
            ws.close();
          }
        };

        ws.onerror = () => {
          message.error('WebSocket 连接失败');
          setProcessing(false);
        };
      }
    } catch (error) {
      message.error('OCR 启动失败: ' + error.message);
      setProcessing(false);
    }
  };

  return (
    <div className="App">
      <div className="container">
        <Card title="🚀 DeepSeek OCR Web UI" className="main-card">
          
          {/* 提示词选择 */}
          <Card type="inner" title="1. 选择识别模式" style={{ marginBottom: 16 }}>
            <Radio.Group 
              value={promptType} 
              onChange={(e) => setPromptType(e.target.value)}
              style={{ marginBottom: 16 }}
            >
              <Radio.Button value="free">基础 OCR</Radio.Button>
              <Radio.Button value="markdown">文档转 Markdown</Radio.Button>
              <Radio.Button value="table">表格识别</Radio.Button>
              <Radio.Button value="figure">图表解析</Radio.Button>
              <Radio.Button value="custom">自定义</Radio.Button>
            </Radio.Group>
            
            {promptType === 'custom' && (
              <TextArea
                placeholder="输入自定义提示词，例如: <image>\nFree OCR."
                value={customPrompt}
                onChange={(e) => setCustomPrompt(e.target.value)}
                rows={2}
              />
            )}
          </Card>

          {/* 文件上传 */}
          <Card type="inner" title="2. 上传文件" style={{ marginBottom: 16 }}>
            <Dragger {...uploadProps}>
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
              <p className="ant-upload-hint">
                支持 PDF, PNG, JPG, JPEG 格式
              </p>
            </Dragger>
            
            <Button
              type="primary"
              onClick={handleUpload}
              disabled={\!file || uploading || processing}
              loading={uploading || processing}
              style={{ marginTop: 16, width: '100%' }}
              size="large"
            >
              {uploading ? '上传中...' : processing ? 'OCR 识别中...' : '开始识别'}
            </Button>
          </Card>

          {/* 进度条 */}
          {processing && (
            <Card type="inner" title="3. 识别进度" style={{ marginBottom: 16 }}>
              <Progress percent={progress} status="active" />
            </Card>
          )}

          {/* 结果展示 */}
          {result && (
            <Card 
              type="inner" 
              title={
                <span>
                  <FileTextOutlined /> 识别结果
                </span>
              }
            >
              <div className="result-container">
                {promptType === 'markdown' ? (
                  <ReactMarkdown>{result}</ReactMarkdown>
                ) : (
                  <pre style={{ whiteSpace: 'pre-wrap', wordWrap: 'break-word' }}>
                    {result}
                  </pre>
                )}
              </div>
            </Card>
          )}
        </Card>

        {/* 底部信息 */}
        <div style={{ textAlign: 'center', marginTop: 24, color: '#888' }}>
          <p>Powered by DeepSeek-OCR + vLLM</p>
        </div>
      </div>
    </div>
  );
}

export default App;
