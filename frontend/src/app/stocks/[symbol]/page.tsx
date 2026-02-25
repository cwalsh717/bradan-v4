interface StockProfilePageProps {
  params: Promise<{ symbol: string }>;
}

export default async function StockProfilePage({
  params,
}: StockProfilePageProps) {
  const { symbol } = await params;

  return (
    <main className="p-8">
      <h1 className="text-2xl font-bold">{symbol.toUpperCase()}</h1>
      <p className="mt-2 text-foreground/60">
        Stock profile — coming in Phase 6.
      </p>
    </main>
  );
}
