from record import *
from copy import copy
import locale
locale.setlocale(locale.LC_ALL, '')

def site_set_promoter(args, reg, dist2tss, t):

    if dist2tss >= -args.prombeg and dist2tss <= args.promend:
        if not hasattr(reg, 'promoter'):
            reg.promoter = []
        reg.promoter.append(t)

def reg_set_promoter(args, reg, dist2tss1, dist2tss2, t, qlen):

    if dist2tss2 >= -args.prombeg and dist2tss1 <= args.promend:
        if not hasattr(reg, 'promoter'):
            reg.promoter = []
        olen = min(dist2tss2, args.promend)-max(dist2tss1, -args.prombeg)+1
        reg.promoter.append((t, olen, float(olen)/qlen*100))

def get_transcripts(args, q, db):
    
    if hasattr(q, 'pos'):
        tpts = [t for t in db.get_transcripts(q.tok, q.pos, q.pos)]
    else:
        tpts = [t for t in db.get_transcripts(q.tok, q.beg, q.end)]

    genes = list(set([t.gene for t in tpts]))
    if args.longest: # pick the longest transcript for each gene
        tpts = [sorted([_ for _ in g.tpts if _ in tpts], key=lambda t: len(t), reverse=True)[0]
                for g in genes]

    return (tpts, genes)

def are_all_transcripts_overlap(tpts):

    max_beg = None
    min_end = None
    for t in tpts:
        if max_beg is None or max_beg < t.beg:
            max_beg = t.beg
        if min_end is None or min_end > t.end:
            min_end = t.end

    if max_beg < min_end:
        return True
    else:
        return False

def format_group(d):

    return locale.format('%d', d, grouping=True)

class IntergenicSite():

    def __init__(self):

        self.e5_name = None
        self.e5_dist = None
        self.e5_strand = None
        
        self.e3_name = None
        self.e3_dist = None
        self.e3_strand = None


    def e5_stream(self):
        if self.e5_strand is None:
            return None
        elif self.e5_strand == '+':
            return 'downstream'
        else:
            return 'upstream'

    def e3_stream(self):
        if self.e3_strand is None:
            return None
        elif self.e3_strand == '-':
            return 'downstream'
        else:
            return 'upstream'
        
    def format(self):

        return "intergenic_between_%s(%s)_and_%s(%s)" % (
            self.e5_name,
            '%s_bp' % format_group(self.e5_dist) if self.e5_strand is None
            else '%s_bp_%s' % (format_group(self.e5_dist), self.e5_stream()),
            self.e3_name,
            '%s_bp' % format_group(self.e3_dist) if self.e3_strand is None
            else '%s_bp_%s' % (format_group(self.e3_dist), self.e3_stream()))

def describe_intergenic_site(args, db, chrm, beg=None, end=None, pos=None, tu=None, td=None):

    if pos is not None:
        beg = pos
        end = pos
        
    _tu, _td = db.get_closest_transcripts(chrm, beg, end)
    if tu is None:
        tu = _tu
    if td is None:
        td = _td
        
    site = IntergenicSite()
    if tu:
        site.e5 = tu
        site.e5_name = tu.gene.name
        site.e5_dist = beg-tu.end
        site.e5_strand = tu.gene.strand()
    else:
        site.e5 = None
        site.e5_name = "5'-telomere"
        site.e5_dist = beg

    if td:
        site.e3 = td
        site.e3_name = td.gene.name
        site.e3_dist = td.beg-end
        site.e3_strand = td.gene.strand()
    else:
        site.e3 = None
        site.e3_name = "3'-telomere"
        site.e3_dist = reflen(chrm)-end

    return site


def describe_genic_site(args, chrm, gpos, t, db):

    reg = RegAnno()
    reg.t = t

    dist2tss = gpos-t.exons[0][0] if t.strand == '+' else t.exons[-1][1]-gpos
    site_set_promoter(args, reg, dist2tss, t)

    if gpos < t.exons[0][0]:
        reg.intergenic = describe_intergenic_site(args, db, chrm, pos=gpos, td=t)
        return reg
    if gpos > t.exons[-1][1]:
        reg.intergenic = describe_intergenic_site(args, db, chrm, pos=gpos, tu=t)
        return reg

    if t.transcript_type == 'protein_coding':
        if gpos < t.cds_beg:
            reg.UTR = '5' if t.strand == '+' else '3'
        if gpos > t.cds_end:
            reg.UTR = '3' if t.strand == '+' else '5'

    for i, exon in enumerate(t.exons):
        exind = i+1 if t.strand == '+' else len(t.exons) - i
        if exon[0] <= gpos and exon[1] >= gpos: # exonic
            reg.exonic = True
            
            if t.transcript_type == 'protein_coding':
                if gpos >= t.cds_beg and gpos <= t.cds_end:
                    reg.cds = True
                if gpos == t.cds_beg:
                    if t.strand == '+':
                        reg.cds_beg = t.cds_beg
                    else:
                        reg.cds_end = t.cds_beg
                if gpos == t.cds_end:
                    if t.strand == '+':
                        reg.cds_end = t.cds_end
                    else:
                        reg.cds_beg = t.cds_end

                if gpos == t.beg:
                    if t.strand == '+':
                        reg.tss = t.beg
                    else:
                        reg.tes = t.beg
                if gpos == t.end:
                    if t.strand == '+':
                        reg.tes = t.end
                    else:
                        reg.tss = t.end

            if gpos == exon[1]:
                if t.strand == '+':
                    reg.splice = 'next_to_donor'
                else:
                    reg.splice = 'next_to_acceptor'
                reg.splice += '_splice_site_of_exon_%d_at_%s:%d' % (exind, t.chrm, exon[1]+1)
            if gpos == exon[0]:
                if t.strand == '+':
                    reg.splice = 'next_to_acceptor'
                else:
                    reg.splice = 'next_to_donor'
                reg.splice += '_splice_site_of_exon_%d_at_%s:%d' % (exind, t.chrm, exon[0]-1)
            reg.exon = exind
            return reg
        if i > 0:
            pexon = t.exons[i-1]
            if gpos > pexon[1] and gpos < exon[0]: # intronic
                reg.intronic = True
                if t.strand == '+':
                    reg.intron_exon1 = exind-1
                    reg.intron_exon2 = exind
                else:
                    reg.intron_exon1 = exind
                    reg.intron_exon2 = exind+1
                if gpos in [pexon[1]+1, pexon[1]+2]:
                    if t.strand == '+':
                        reg.splice = 'donor'
                    else:
                        reg.splice = 'acceptor'
                    reg.splice += '_splice_site_of_exon_%d_at_%s:%d' % (exind, t.chrm, pexon[1]+1)
                if gpos in [exon[0]-2, exon[0]-1]:
                    if t.strand == '-':
                        reg.splice = 'donor'
                    else:
                        reg.splice = 'acceptor'
                    reg.splice += '_splice_site_of_exon_%d_at_%s:%d' % (exind, t.chrm, exon[0]-1)

                return reg

    raise Exception()       # you shouldn't reach here


def describe_genic_range(args, chrm, beg, end, t, db, genes):

    reg = RegSpanAnno()
    reg.t = t
    reg.b1 = describe_genic_site(args, chrm, beg, t, db)
    reg.b2 = describe_genic_site(args, chrm, end, t, db)

    dist2tss1 = beg-t.exons[0][0] if t.strand == '+' else t.exons[-1][1]-end
    dist2tss2 = end-t.exons[0][0] if t.strand == '+' else t.exons[-1][1]-beg
    reg_set_promoter(args, reg, dist2tss1, dist2tss2, t, end-beg+1)

    reg.spanning = [g for g in genes if g.get_beg() >= beg and g.get_end() <= end]
    n = len(t.exons)
    reg.splice_donors = []
    reg.splice_acceptors = []
    reg.splice_both = []
    for i, exon in enumerate(t.exons):
        if exon[0] >= beg and exon[1] <= end:
            if t.strand == '+':
                reg.splice_both.append(i+1)
            else:
                reg.splice_both.append(n-i)
        elif exon[0] >= beg and exon[0] <= end and i != 0:
            if t.strand == '+':
                reg.splice_acceptors.append((i+1, t.chrm, exon[0]-1))
            else:
                reg.splice_donors.append((n-i, t.chrm, exon[0]-1))
        elif exon[1] >= beg and exon[1] <= end and i != n-1:
            if t.strand == '+':
                reg.splice_donors.append((i+1, t.chrm, exon[1]+1))
            else:
                reg.splice_acceptors.append((n-i, t.chrm, exon[1]+1))

    if t.transcript_type == 'protein_coding':
        if beg <= t.cds_beg and end >= t.cds_beg:
            reg.cross_start = True
        if beg <= t.cds_end and end >= t.cds_end:
            reg.cross_end = True

        for exon in enumerate(t.exons):
            if exon[0] <= end and exon[1] >= beg:
                reg.cover_exon = True
        if reg.cover_exon and beg <= t.cds_end and end >= t.cds_beg:
            reg.cover_cds = True
                

    return reg

def describe_genic(args, chrm, beg, end, t, db, genes=[]):

    if beg == end:
        return describe_genic_site(args, chrm, beg, t, db)
    else:
        return describe_genic_range(args, chrm, beg, end, t, db, genes)

def describe(args, q, db):

    """ return
    RegAnno (if q is a point, i.e., q.beg == q.end)
    or
    RegSpanAnno (if q is a range)
    """

    tpts, genes = get_transcripts(args, q, db)

    if tpts:
        if hasattr(q, 'pos') or q.beg == q.end: # point

            if not hasattr(q,'pos'):
                q.pos = q.beg
                
            for t in tpts:
                reg = describe_genic_site(args, q.tok, q.pos, t, db)
                yield reg
                
        elif are_all_transcripts_overlap(tpts): # short range, involving overlapping genes
            for t in tpts:
                reg = describe_genic_range(args, q.tok, q.beg, q.end, t, db, genes=genes)
                yield reg

        else:   # long range, involving multiple non-overlapping genes

            # do not care about promoter
            q1 = copy(q)
            q1.end = q1.beg
            q2 = copy(q)
            q2.beg = q2.end
            for reg_beg in describe(args, q1, db):
                for reg_end in describe(args, q2, db):
                    reg = RegSpanAnno()
                    reg.spanning = [g for g in genes if g.get_beg() >= q.beg and g.get_end() <= q.end]
                    reg.b1 = reg_beg
                    reg.b2 = reg_end
                    yield reg

    else:        # purely intergenic
            
        if hasattr(q, 'pos') or q.beg == q.end: # point

            if not hasattr(q,'pos'):
                q.pos = q.beg

            reg = RegAnno()
            reg.intergenic = describe_intergenic_site(args, db, q.tok, pos=q.pos)
            
            itg = reg.intergenic
            if itg.e5 is not None and itg.e5_strand == '-':
                dist2tss = -itg.e5_dist
                site_set_promoter(args, reg, dist2tss, itg.e5)
                
            if itg.e3 is not None and itg.e3_strand == '+':
                dist2tss = -itg.e3_dist
                site_set_promoter(args, reg, dist2tss, itg.e3)
                
        else:                   # range
            reg = RegSpanAnno()
            reg.intergenic = describe_intergenic_site(args, db, q.tok, beg=q.beg, end=q.end)

            itg = reg.intergenic
            if itg.e5 is not None and itg.e5_strand == '-':
                dist2tss1 = -itg.e5_dist-(q.end-q.beg)
                dist2tss2 = -itg.e5_dist
                reg_set_promoter(args, reg, dist2tss1, dist2tss2, itg.e5, q.end-q.beg+1)
                
            if itg.e3 is not None and itg.e3_strand == '+':
                dist2tss1 = -itg.e3_dist-(q.end-q.beg)
                dist2tss2 = -itg.e3_dist
                reg_set_promoter(args, reg, dist2tss1, dist2tss2, itg.e3, q.end-q.beg+1)

        yield reg


