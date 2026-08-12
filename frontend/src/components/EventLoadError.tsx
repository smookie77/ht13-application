export function EventLoadError({ hint }: { hint: string }) {
  return (
    <main className="flex min-h-[60vh] items-center justify-center px-6 py-20">
      <div className="max-w-md rounded-2xl border border-amber-300 bg-amber-50 p-6 text-center">
        <h1 className="text-lg font-semibold text-amber-900">Event unavailable</h1>
        <p className="mt-2 text-sm text-amber-800">{hint}</p>
      </div>
    </main>
  );
}
