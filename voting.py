from collections import defaultdict

def calculate_rcv_winner(votes, candidates):
    if not votes or not candidates:
        return None
    active_candidates = set(candidates)
    current_votes = votes[:]
    while len(active_candidates) > 1:
        first_prefs = defaultdict(int)
        exhausted = 0
        for vote in current_votes:
            found = False
            for choice in vote:
                if choice in active_candidates:
                    first_prefs[choice] += 1
                    found = True
                    break
            if not found:
                exhausted += 1
        if not first_prefs:
            break
        total_votes = len(current_votes) - exhausted
        if total_votes == 0:
            break
        for candidate, count in first_prefs.items():
            if count > total_votes / 2:
                return candidate
        min_candidate = min(first_prefs.keys(), key=lambda x: first_prefs[x])
        active_candidates.remove(min_candidate)
    return active_candidates.pop() if active_candidates else None

def get_poll_results(votes, candidates):
    rounds = []
    active_candidates = set(candidates)
    current_votes = votes[:]
    round_num = 1
    while len(active_candidates) > 0:
        first_prefs = defaultdict(int)
        exhausted = 0
        for vote in current_votes:
            found = False
            for choice in vote:
                if choice in active_candidates:
                    first_prefs[choice] += 1
                    found = True
                    break
            if not found:
                exhausted += 1
        total_votes = len(current_votes) - exhausted
        round_data = {
            'round': round_num,
            'results': dict(first_prefs),
            'exhausted': exhausted,
            'total': total_votes,
            'active_candidates': list(active_candidates)
        }
        rounds.append(round_data)
        if len(active_candidates) <= 1 or total_votes == 0:
            break
        if first_prefs:
            min_candidate = min(first_prefs.keys(), key=lambda x: first_prefs[x])
            active_candidates.remove(min_candidate)
            round_num += 1
    return rounds

def calculate_borda_count(votes, candidates):
    if not votes or not candidates:
        return None, {}
    scores = {cand: 0 for cand in candidates}
    n = len(candidates)
    for ranking in votes:
        for rank, cand in enumerate(ranking):
            if cand in candidates:
                points = n - rank - 1
                scores[cand] += points
    if not scores:
        return None, scores
    winner = max(scores.items(), key=lambda x: (-x[1], x[0]))[0]
    return winner, scores

def get_borda_rankings(votes, candidates):
    winner, scores = calculate_borda_count(votes, candidates)
    sorted_results = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
    return sorted_results

def calculate_condorcet_winner(votes, candidates):
    if not votes or not candidates:
        return None, {}
    pairwise = {c1: {c2: 0 for c2 in candidates if c2 != c1} for c1 in candidates}
    for ranking in votes:
        for i in range(len(ranking)):
            for j in range(i + 1, len(ranking)):
                higher = ranking[i]
                lower = ranking[j]
                if higher in pairwise and lower in pairwise[higher]:
                    pairwise[higher][lower] += 1
    wins = {cand: 0 for cand in candidates}
    for c1 in candidates:
        for c2 in candidates:
            if c1 == c2:
                continue
            if pairwise[c1][c2] > pairwise[c2][c1]:
                wins[c1] += 1
    for cand in candidates:
        if wins[cand] == len(candidates) - 1:
            return cand, pairwise
    return None, pairwise

def get_pairwise_results(votes, candidates):
    condorcet_winner, pairwise = calculate_condorcet_winner(votes, candidates)
    results = []
    for c1 in candidates:
        for c2 in candidates:
            if c1 < c2:
                results.append({
                    'candidate1': c1,
                    'candidate2': c2,
                    'c1_wins': pairwise[c1][c2],
                    'c2_wins': pairwise[c2][c1],
                    'winner': c1 if pairwise[c1][c2] > pairwise[c2][c1] else c2
                })
    return results

def calculate_schulze_winners(votes, candidates):
    if not votes or not candidates:
        return [], []
    n = len(candidates)
    idx = {c: i for i, c in enumerate(candidates)}
    d = [[0 for _ in range(n)] for _ in range(n)]
    for ranking in votes:
        for i in range(len(ranking)):
            for j in range(i + 1, len(ranking)):
                a, b = idx[ranking[i]], idx[ranking[j]]
                d[a][b] += 1
    p = [[0 for _ in range(n)] for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j and d[i][j] > d[j][i]:
                p[i][j] = d[i][j]
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            for k in range(n):
                if i == k or j == k:
                    continue
                potential = min(p[j][i], p[i][k])
                if potential > p[j][k]:
                    p[j][k] = potential
    winners = []
    for i in range(n):
        is_winner = True
        for j in range(n):
            if i != j and p[j][i] > p[i][j]:
                is_winner = False
                break
        if is_winner:
            winners.append(candidates[i])
    return winners, p

def get_schulze_details(votes, candidates):
    winners, p = calculate_schulze_winners(votes, candidates)
    n = len(candidates)
    idx = {c: i for i, c in enumerate(candidates)}
    paths = []
    for i in range(n):
        for j in range(n):
            if i != j:
                paths.append({
                    'from': candidates[i],
                    'to': candidates[j],
                    'strength': p[i][j]
                })
    return winners, sorted(paths, key=lambda x: -x['strength'])

def calculate_all_winners(votes, candidates):
    irv_winner = calculate_rcv_winner(votes, candidates)
    borda_winner, borda_scores = calculate_borda_count(votes, candidates)
    condorcet_winner, _ = calculate_condorcet_winner(votes, candidates)
    schulze_winners, _ = calculate_schulze_winners(votes, candidates)
    return {
        'irv': irv_winner,
        'borda': borda_winner,
        'condorcet': condorcet_winner,
        'schulze': schulze_winners,
        'borda_scores': borda_scores
    }
