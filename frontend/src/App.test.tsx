import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import App from './App';

test('renders SecureHR heading', () => {
  render(<App />);
  const headingElement = screen.getByText(/SecureHR/i);
  expect(headingElement).toBeInTheDocument();
});

test('renders platform description', () => {
  render(<App />);
  const descriptionElement = screen.getByText(/Privacy-preserving talent matching platform/i);
  expect(descriptionElement).toBeInTheDocument();
});