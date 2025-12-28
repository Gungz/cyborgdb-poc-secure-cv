import React, { useState, useRef } from 'react';
import { candidateApi } from '../../services/api';
import { ApiError } from '../../types';

interface CVUploadProps {
  onUploadSuccess?: () => void;
}

const CVUpload: React.FC<CVUploadProps> = ({ onUploadSuccess }) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState<string>('');
  const [success, setSuccess] = useState<string>('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const allowedTypes = ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
  const maxFileSize = 10 * 1024 * 1024; // 10MB

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    setError('');
    setSuccess('');

    if (!file) {
      setSelectedFile(null);
      return;
    }

    // Validate file type
    if (!allowedTypes.includes(file.type)) {
      setError('Please select a PDF, DOC, or DOCX file');
      setSelectedFile(null);
      return;
    }

    // Validate file size
    if (file.size > maxFileSize) {
      setError('File size must be less than 10MB');
      setSelectedFile(null);
      return;
    }

    setSelectedFile(file);
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setError('Please select a file to upload');
      return;
    }

    setUploading(true);
    setUploadProgress(0);
    setError('');
    setSuccess('');

    try {
      await candidateApi.uploadCV(selectedFile, (progress) => {
        setUploadProgress(progress);
      });

      setSuccess('CV processed successfully!');
      setSelectedFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
      onUploadSuccess?.();
    } catch (err: any) {
      const apiError = err.response?.data as ApiError;
      setError(apiError?.detail || 'Upload failed. Please try again.');
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      const file = files[0];
      
      // Create a synthetic event to reuse validation logic
      const syntheticEvent = {
        target: { files: [file] }
      } as unknown as React.ChangeEvent<HTMLInputElement>;
      
      handleFileSelect(syntheticEvent);
    }
  };

  return (
    <div className="cv-upload">
      <h3>Upload Your CV</h3>
      
      <div 
        className={`upload-area ${selectedFile ? 'has-file' : ''}`}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
      >
        <input
          ref={fileInputRef}
          type="file"
          id="cv-file"
          accept=".pdf,.doc,.docx"
          onChange={handleFileSelect}
          disabled={uploading}
          aria-describedby="file-help"
        />
        
        <div className="upload-content">
          {selectedFile ? (
            <div className="selected-file">
              <p><strong>Selected:</strong> {selectedFile.name}</p>
              <p><strong>Size:</strong> {(selectedFile.size / 1024 / 1024).toFixed(2)} MB</p>
            </div>
          ) : (
            <div className="upload-prompt">
              <p>Drag and drop your CV here, or click to browse</p>
              <small id="file-help">Supported formats: PDF, DOC, DOCX (max 10MB)</small>
            </div>
          )}
        </div>
      </div>

      {uploading && (
        <div className="upload-progress" role="progressbar" aria-valuenow={uploadProgress} aria-valuemin={0} aria-valuemax={100}>
          <div className="progress-bar">
            <div 
              className="progress-fill" 
              style={{ width: `${uploadProgress}%` }}
            ></div>
          </div>
          <p>Uploading... {uploadProgress}%</p>
        </div>
      )}

      {error && (
        <div className="error-message" role="alert" aria-live="polite">
          {error}
        </div>
      )}

      {success && (
        <div className="success-message" role="alert" aria-live="polite">
          {success}
        </div>
      )}

      <div className="upload-actions">
        <button 
          onClick={handleUpload} 
          disabled={!selectedFile || uploading}
          className="upload-btn"
        >
          {uploading ? 'Uploading...' : 'Upload CV'}
        </button>
        
        {selectedFile && !uploading && (
          <button 
            onClick={() => {
              setSelectedFile(null);
              if (fileInputRef.current) {
                fileInputRef.current.value = '';
              }
            }}
            className="cancel-btn"
          >
            Cancel
          </button>
        )}
      </div>
    </div>
  );
};

export default CVUpload;