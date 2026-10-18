import React, { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RotateCcw } from 'lucide-react';

interface Props {
  children: ReactNode;
  fallbackTitle?: string;
  onReset?: () => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error in component tree:', error, errorInfo);
  }

  public handleReset = () => {
    this.setState({ hasError: false, error: null });
    this.props.onReset?.();
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div className="panel error-boundary-panel pop-in" style={{ margin: '20px 0', borderColor: 'var(--red, #cf3c3c)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
            <AlertTriangle color="var(--red, #cf3c3c)" size={24} />
            <h2 style={{ fontSize: '1.1rem', margin: 0, color: 'var(--red, #cf3c3c)' }}>
              {this.props.fallbackTitle || 'Something went wrong rendering this section'}
            </h2>
          </div>
          <p className="muted" style={{ margin: '8px 0 16px' }}>
            {this.state.error?.message || 'An unexpected rendering error occurred.'}
          </p>
          <button
            className="button secondary"
            onClick={this.handleReset}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}
          >
            <RotateCcw size={15} /> Try reloading section
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
