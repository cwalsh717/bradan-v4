interface DCFPageProps {
  params: Promise<{ symbol: string }>;
}

export default async function DCFPage({ params }: DCFPageProps) {
  const { symbol } = await params;

  return (
    <main className="p-8">
      <h1 className="text-2xl font-bold">DCF — {symbol.toUpperCase()}</h1>
      <p className="mt-2 text-foreground/60">
        Valuation model — coming in Phase 6.
      </p>
    </main>
  );
}
