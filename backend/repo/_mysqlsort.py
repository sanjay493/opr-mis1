"""MySQL filesort tie order, reproduced in Python.

PARITY SHIM - remove after the 7g gate with an announced tie-break change.
It emulates a v1 optimizer / server artefact (std::sort's order of tied
rows) only so that v2's output is byte-identical to v1's for the parity
proof; nothing about the data requires it.

Some v1 queries sort rows whose sort keys tie (GROUP BY executed as "Sort,
then Group aggregate"; ORDER BY with equal keys). MySQL's filesort sorts its
in-memory buffer with std::sort, which is not stable, and the order of
tied rows then decides v1's output: which row of a group comes first, and
the order SUM(double) adds a group's values in (so the last ulp of a sum).

mysql_sort(rows, key) returns `rows` (given in the order MySQL read them)
in the order the MySQL server's std::sort leaves them, for the comparison
key(a) < key(b). The server here is the Windows build (MSVC), so this is the
MSVC STL std::sort: introsort with median-of-3 / median-of-9 pivots, a
"fat" partition that gathers keys equal to the pivot, insertion sort for
ranges of at most 32 rows, heap sort past 1.5 * log2(n) partition levels.
Sort keys must compare like MySQL's sort keys (WEIGHT_STRING bytes for
strings under their collation).

Proven against the v1 oracle by tools/repo_oracle replay (repo.production
plant_item_sum_counts and records_calendar_month_totals).
"""

_ISORT_MAX = 32


def mysql_sort(rows, key):
    a = [(key(r), r) for r in rows]

    def lt(i, j):
        return a[i][0] < a[j][0]

    def swap(i, j):
        a[i], a[j] = a[j], a[i]

    def insertion(first, last):
        mid = first
        while first != last:
            mid += 1
            if mid == last:
                return
            hole = mid
            val = a[mid]
            if val[0] < a[first][0]:
                a[first + 1:mid + 1] = a[first:mid]
                a[first] = val
            else:
                prev = hole - 1
                while val[0] < a[prev][0]:
                    a[hole] = a[prev]
                    hole = prev
                    prev -= 1
                a[hole] = val

    def med3(f, m, l):
        if lt(m, f):
            swap(m, f)
        if lt(l, m):
            swap(l, m)
            if lt(m, f):
                swap(m, f)

    def guess_median(f, m, l):          # l is inclusive
        count = l - f
        if 40 < count:
            step = (count + 1) >> 3
            two = step << 1
            med3(f, f + step, f + two)
            med3(m - step, m, m + step)
            med3(l - two, l - step, l)
            med3(f + step, m, l - step)
        else:
            med3(f, m, l)

    def partition(first, last):
        mid = first + ((last - first) >> 1)
        guess_median(first, mid, last - 1)
        pf = mid
        pl = pf + 1
        while first < pf and not lt(pf - 1, pf) and not lt(pf, pf - 1):
            pf -= 1
        while pl < last and not lt(pl, pf) and not lt(pf, pl):
            pl += 1
        gf = pl
        gl = pf
        while True:
            while gf < last:
                if lt(pf, gf):
                    pass
                elif lt(gf, pf):
                    break
                elif pl != gf:
                    swap(pl, gf)
                    pl += 1
                else:
                    pl += 1
                gf += 1
            while first < gl:
                gp = gl - 1
                if lt(gp, pf):
                    pass
                elif lt(pf, gp):
                    break
                else:
                    pf -= 1
                    if pf != gp:
                        swap(pf, gp)
                gl -= 1
            if gl == first and gf == last:
                return pf, pl
            if gl == first:              # no room at bottom, rotate pivot upward
                if pl != gf:
                    swap(pf, pl)
                pl += 1
                swap(pf, gf)
                pf += 1
                gf += 1
            elif gf == last:             # no room at top, rotate pivot downward
                gl -= 1
                pf -= 1
                if gl != pf:
                    swap(gl, pf)
                pl -= 1
                swap(pf, pl)
            else:
                gl -= 1
                swap(gf, gl)
                gf += 1

    def push_heap_by_index(first, hole, top, val):
        idx = (hole - 1) >> 1
        while top < hole and a[first + idx][0] < val[0]:
            a[first + hole] = a[first + idx]
            hole = idx
            idx = (hole - 1) >> 1
        a[first + hole] = val

    def pop_heap_hole_by_index(first, hole, bottom, val):
        top = hole
        idx = hole
        max_non_leaf = (bottom - 1) >> 1
        while idx < max_non_leaf:
            idx = 2 * idx + 2
            if a[first + idx][0] < a[first + idx - 1][0]:
                idx -= 1
            a[first + hole] = a[first + idx]
            hole = idx
        if idx == max_non_leaf and bottom % 2 == 0:
            a[first + hole] = a[first + bottom - 1]
            hole = bottom - 1
        push_heap_by_index(first, hole, top, val)

    def heap_sort(first, last):
        bottom = last - first
        hole = bottom >> 1
        while 0 < hole:
            hole -= 1
            pop_heap_hole_by_index(first, hole, bottom, a[first + hole])
        while last - first >= 2:
            last -= 1
            val = a[last]
            a[last] = a[first]
            pop_heap_hole_by_index(first, 0, last - first, val)

    def sort(first, last, ideal):
        while True:
            if last - first <= _ISORT_MAX:
                insertion(first, last)
                return
            if ideal <= 0:
                heap_sort(first, last)
                return
            m0, m1 = partition(first, last)
            ideal = (ideal >> 1) + (ideal >> 2)
            if m0 - first < last - m1:
                sort(first, m0, ideal)
                first = m1
            else:
                sort(m1, last, ideal)
                last = m0

    sort(0, len(a), len(a))
    return [r for _, r in a]
