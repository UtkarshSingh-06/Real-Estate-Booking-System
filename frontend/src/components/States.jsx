import React from 'react';

export function LoadingState({ label = 'Loading...' }) {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-3">
      <div className="loading-spinner" />
      <p className="text-sm text-muted-foreground">{label}</p>
    </div>
  );
}

export function EmptyState({ icon: Icon, title, description }) {
  return (
    <div className="text-center py-12 px-4">
      {Icon ? <Icon className="h-16 w-16 mx-auto mb-4 text-gray-400" /> : null}
      <p className="text-lg font-medium text-gray-700">{title}</p>
      {description ? <p className="text-gray-500 mt-2">{description}</p> : null}
    </div>
  );
}

export function ErrorState({ message = 'Something went wrong', onRetry }) {
  return (
    <div className="text-center py-12 px-4">
      <p className="text-red-600 mb-4">{message}</p>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="underline text-sm text-gray-700"
        >
          Try again
        </button>
      ) : null}
    </div>
  );
}
