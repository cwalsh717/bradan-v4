/**
 * Reusable error state with optional retry.
 */

interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
}

export function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <div
      className="rounded-lg border border-red-200 bg-red-50 p-6 text-center dark:border-red-800 dark:bg-red-900/20"
      data-testid="error-state"
    >
      <p className="text-sm text-red-700 dark:text-red-300">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-3 rounded-md bg-red-100 px-4 py-1.5 text-sm font-medium text-red-800 transition-colors hover:bg-red-200 dark:bg-red-900/40 dark:text-red-200 dark:hover:bg-red-900/60"
          data-testid="retry-button"
        >
          Retry
        </button>
      )}
    </div>
  );
}
