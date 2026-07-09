// Oefenwachtrij: fout beantwoorde items komen `gap` posities later terug,
// de sessie is klaar als elk item één keer goed beantwoord is.

export function shuffle(items) {
  const result = [...items];
  for (let i = result.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [result[i], result[j]] = [result[j], result[i]];
  }
  return result;
}

export function createQueue(items, {gap = 3} = {}) {
  const pending = [...items];
  const wrongCounts = new Map();
  let mastered = 0;
  let wrongTotal = 0;
  const total = items.length;

  return {
    get current() {
      return pending.length ? pending[0] : null;
    },
    get done() {
      return pending.length === 0;
    },
    get progress() {
      return {mastered, total, wrong: wrongTotal};
    },
    get firstTryCorrect() {
      return [...items].filter(
        (item) => !wrongCounts.has(item) && !pending.includes(item),
      ).length;
    },
    correct() {
      pending.shift();
      mastered++;
    },
    wrong() {
      const item = pending.shift();
      wrongTotal++;
      wrongCounts.set(item, (wrongCounts.get(item) || 0) + 1);
      pending.splice(Math.min(gap, pending.length), 0, item);
    },
  };
}
