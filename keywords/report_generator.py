"""
Keyword Report Generator Service
Handles CSV and PDF report generation with data processing
"""

import io
import csv
import json
import logging
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict

import pandas as pd
from django.utils import timezone
from django.db.models import Q, Prefetch

# PDF generation imports
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.widgets.markers import makeMarker
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

logger = logging.getLogger(__name__)


class KeywordReportGenerator:
    """Generate keyword ranking reports in CSV and PDF formats"""
    
    def __init__(self, report):
        """
        Initialize report generator
        
        Args:
            report: KeywordReport instance
        """
        self.report = report
        self.project = report.project
        self.start_date = report.start_date
        self.end_date = report.end_date
        
        # Calculate date range (list of dates)
        self.date_range = self._generate_date_range()
        
        # Storage for processed data
        self.keywords_data = []
        self.ranking_data = {}
        self.summary_stats = {}
        
    def _generate_date_range(self) -> List[date]:
        """Generate list of dates between start and end date"""
        dates = []
        current = self.start_date
        
        while current <= self.end_date:
            dates.append(current)
            current += timedelta(days=1)
        
        return dates
    
    def generate_reports(self) -> Dict[str, Any]:
        """
        Generate reports in configured formats
        
        Returns:
            Dict with generation results and file paths
        """
        results = {
            'success': False,
            'csv_path': None,
            'pdf_path': None,
            'error': None
        }
        
        try:
            # Load and process data
            logger.info(f"Loading data for report {self.report.id}")
            self._load_keyword_data()
            self._load_ranking_data()
            self._calculate_summary_stats()
            
            # Generate CSV if requested
            if self.report.report_format in ['csv', 'both']:
                logger.info("Generating CSV report")
                csv_content = self._generate_csv()
                results['csv_content'] = csv_content
                results['csv_size'] = len(csv_content)
            
            # Generate PDF if requested
            if self.report.report_format in ['pdf', 'both']:
                logger.info("Generating PDF report")
                pdf_content = self._generate_pdf()
                results['pdf_content'] = pdf_content
                results['pdf_size'] = len(pdf_content)
            
            results['success'] = True
            results['summary'] = self.summary_stats
            
        except Exception as e:
            logger.error(f"Error generating report: {e}", exc_info=True)
            results['error'] = str(e)
        
        return results
    
    def _load_keyword_data(self):
        """Load keywords based on report configuration"""
        from .models import Keyword
        
        # Start with project keywords
        keywords_qs = Keyword.objects.filter(
            project=self.project,
            archive=False
        )
        
        # Apply keyword filter if specified
        if self.report.keywords.exists():
            keywords_qs = keywords_qs.filter(
                id__in=self.report.keywords.values_list('id', flat=True)
            )
        
        # Apply tag filters
        # Note: Tags would need to be implemented in Keyword model
        # For now, we'll skip tag filtering
        
        # Order by keyword name for consistent output
        keywords_qs = keywords_qs.order_by('keyword')
        
        # Store keywords
        self.keywords_data = list(keywords_qs.values(
            'id', 'keyword', 'country', 'country_code',
            'rank', 'rank_url', 'rank_status', 'impact',
            'created_at', 'scraped_at'
        ))
        
        logger.info(f"Loaded {len(self.keywords_data)} keywords")
    
    def _load_ranking_data(self):
        """Load historical ranking data for date range"""
        from .models import Rank
        
        # Get all keyword IDs
        keyword_ids = [kw['id'] for kw in self.keywords_data]
        
        # Load ranks for date range
        start_datetime = timezone.make_aware(
            datetime.combine(self.start_date, datetime.min.time())
        )
        end_datetime = timezone.make_aware(
            datetime.combine(self.end_date, datetime.max.time())
        )
        
        ranks_qs = Rank.objects.filter(
            keyword_id__in=keyword_ids,
            created_at__gte=start_datetime,
            created_at__lte=end_datetime,
            is_organic=True  # Only organic ranks
        ).order_by('keyword_id', 'created_at')
        
        # Organize ranks by keyword and date
        self.ranking_data = defaultdict(lambda: defaultdict(dict))
        
        for rank in ranks_qs:
            rank_date = rank.created_at.date()
            keyword_id = rank.keyword_id
            
            # Store the best (lowest) rank for each day
            if rank_date not in self.ranking_data[keyword_id] or \
               rank.rank < self.ranking_data[keyword_id][rank_date].get('rank', 999):
                self.ranking_data[keyword_id][rank_date] = {
                    'rank': rank.rank,
                    'created_at': rank.created_at
                }
        
        # Fill missing ranks if configured
        if self.report.fill_missing_ranks:
            self._fill_missing_ranks()
        
        logger.info(f"Loaded ranking data for {len(self.ranking_data)} keywords")
    
    def _fill_missing_ranks(self):
        """Fill missing rank data with previous day's rank"""
        for keyword_id in self.ranking_data:
            last_known_rank = None
            
            for date_obj in self.date_range:
                if date_obj in self.ranking_data[keyword_id]:
                    # We have data for this date
                    last_known_rank = self.ranking_data[keyword_id][date_obj]['rank']
                elif last_known_rank is not None:
                    # Use last known rank
                    self.ranking_data[keyword_id][date_obj] = {
                        'rank': last_known_rank,
                        'filled': True  # Mark as filled data
                    }
    
    def _calculate_summary_stats(self):
        """Calculate summary statistics for the report"""
        total_keywords = len(self.keywords_data)
        
        # Calculate ranking improvements/declines
        improvements = 0
        declines = 0
        no_change = 0
        
        for kw_data in self.keywords_data:
            keyword_id = kw_data['id']
            
            if keyword_id not in self.ranking_data:
                continue
            
            # Get first and last rank in period
            dates_with_data = sorted([d for d in self.date_range if d in self.ranking_data[keyword_id]])
            
            if len(dates_with_data) >= 2:
                first_rank = self.ranking_data[keyword_id][dates_with_data[0]]['rank']
                last_rank = self.ranking_data[keyword_id][dates_with_data[-1]]['rank']
                
                if first_rank > 100:
                    first_rank = 101  # Treat >100 as 101
                if last_rank > 100:
                    last_rank = 101
                
                if last_rank < first_rank:
                    improvements += 1
                elif last_rank > first_rank:
                    declines += 1
                else:
                    no_change += 1
        
        self.summary_stats = {
            'total_keywords': total_keywords,
            'date_range': f"{self.start_date.strftime('%Y-%m-%d')} to {self.end_date.strftime('%Y-%m-%d')}",
            'days_covered': len(self.date_range),
            'improvements': improvements,
            'declines': declines,
            'no_change': no_change,
            'report_generated': timezone.now().isoformat()
        }
    
    def _generate_csv(self) -> bytes:
        """
        Generate CSV report matching the sample format
        
        Returns:
            CSV content as bytes
        """
        output = io.StringIO()
        
        # Write header information
        output.write(f"Domain,{self.project.domain}\n")
        output.write(f"Start Date,{self.start_date.strftime('%a %b %d %Y')}\n")
        output.write(f"End Date,{self.end_date.strftime('%a %b %d %Y')}\n")
        
        # Prepare main data headers
        headers = [
            "Search Engine", "Keyword", "Url", "Added On", 
            "Rank", "Impact", "Tags"
        ]
        
        # Add date columns
        for date_obj in self.date_range:
            headers.append(date_obj.strftime('%d %b %Y'))
        
        # Write main data
        writer = csv.writer(output)
        writer.writerow(headers)
        
        # Write keyword data rows
        for kw_data in self.keywords_data:
            keyword_id = kw_data['id']
            
            # Determine current rank and impact
            current_rank = kw_data['rank']
            if current_rank == 0 or current_rank > 100:
                current_rank_str = "NR"
            else:
                current_rank_str = str(current_rank)
            
            # Determine rank change impact
            impact = "no_change"
            if keyword_id in self.ranking_data:
                dates_with_data = sorted([d for d in self.date_range if d in self.ranking_data[keyword_id]])
                if len(dates_with_data) >= 2:
                    first_rank = self.ranking_data[keyword_id][dates_with_data[0]]['rank']
                    last_rank = self.ranking_data[keyword_id][dates_with_data[-1]]['rank']
                    
                    if last_rank < first_rank:
                        impact = "up"
                    elif last_rank > first_rank:
                        impact = "down"
            
            row = [
                f"GOOGLE, {kw_data['country_code']}",
                kw_data['keyword'],
                kw_data.get('rank_url', ''),
                kw_data['created_at'].strftime('%Y-%m-%d') if kw_data['created_at'] else '',
                current_rank_str,
                impact,
                ""  # Tags (empty for now)
            ]
            
            # Add daily rank data
            for date_obj in self.date_range:
                if keyword_id in self.ranking_data and date_obj in self.ranking_data[keyword_id]:
                    rank_value = self.ranking_data[keyword_id][date_obj]['rank']
                    if rank_value == 0 or rank_value > 100:
                        row.append("NR")
                    else:
                        row.append(str(rank_value))
                else:
                    row.append("NR")  # No data means not ranking
            
            writer.writerow(row)
        
        # Get CSV content as bytes
        csv_content = output.getvalue()
        output.close()
        
        return csv_content.encode('utf-8')
    
    def _generate_pdf(self) -> bytes:
        """
        Generate PDF report with charts and formatted data
        
        Returns:
            PDF content as bytes
        """
        buffer = io.BytesIO()
        
        # Create PDF document
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18,
        )
        
        # Container for the 'Flowable' objects
        elements = []
        
        # Define styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Title'],
            fontSize=24,
            textColor=colors.HexColor('#1f2937'),
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#1f2937'),
            spaceAfter=12,
            spaceBefore=12
        )
        
        # Add title
        elements.append(Paragraph(f"Keyword Ranking Report", title_style))
        elements.append(Paragraph(f"{self.project.domain}", styles['Heading2']))
        elements.append(Spacer(1, 20))
        
        # Add report information
        info_data = [
            ['Report Period:', f"{self.start_date.strftime('%B %d, %Y')} - {self.end_date.strftime('%B %d, %Y')}"],
            ['Total Keywords:', str(self.summary_stats['total_keywords'])],
            ['Days Covered:', str(self.summary_stats['days_covered'])],
            ['Generated:', datetime.now().strftime('%B %d, %Y at %I:%M %p')]
        ]
        
        info_table = Table(info_data, colWidths=[2*inch, 4*inch])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        
        elements.append(info_table)
        elements.append(Spacer(1, 30))
        
        # Add summary statistics
        elements.append(Paragraph("Executive Summary", heading_style))
        
        summary_data = [
            ['Metric', 'Count', 'Percentage'],
            ['Keywords Improved', str(self.summary_stats['improvements']), 
             f"{(self.summary_stats['improvements']/max(self.summary_stats['total_keywords'],1)*100):.1f}%"],
            ['Keywords Declined', str(self.summary_stats['declines']),
             f"{(self.summary_stats['declines']/max(self.summary_stats['total_keywords'],1)*100):.1f}%"],
            ['No Change', str(self.summary_stats['no_change']),
             f"{(self.summary_stats['no_change']/max(self.summary_stats['total_keywords'],1)*100):.1f}%"],
        ]
        
        summary_table = Table(summary_data, colWidths=[2.5*inch, 1.5*inch, 1.5*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        
        elements.append(summary_table)
        elements.append(PageBreak())
        
        # Add ranking trends chart if configured
        if self.report.include_graphs and len(self.ranking_data) > 0:
            elements.append(Paragraph("Ranking Trends", heading_style))
            chart = self._create_ranking_chart()
            if chart:
                elements.append(chart)
                elements.append(Spacer(1, 20))
        
        # Add detailed keyword table (paginated)
        elements.append(Paragraph("Keyword Performance Details", heading_style))
        
        # Create detailed table with limited rows per page
        detail_headers = ['Keyword', 'Start Rank', 'End Rank', 'Change', 'Status']
        detail_data = [detail_headers]
        
        for kw_data in self.keywords_data[:50]:  # Limit to first 50 keywords
            keyword_id = kw_data['id']
            
            if keyword_id not in self.ranking_data:
                continue
            
            dates_with_data = sorted([d for d in self.date_range if d in self.ranking_data[keyword_id]])
            
            if len(dates_with_data) >= 2:
                first_rank = self.ranking_data[keyword_id][dates_with_data[0]]['rank']
                last_rank = self.ranking_data[keyword_id][dates_with_data[-1]]['rank']
                
                if first_rank > 100:
                    first_rank_str = "NR"
                else:
                    first_rank_str = str(first_rank)
                
                if last_rank > 100:
                    last_rank_str = "NR"
                else:
                    last_rank_str = str(last_rank)
                
                # Calculate change
                if first_rank > 100 and last_rank > 100:
                    change_str = "0"
                    status = "No Change"
                elif first_rank > 100:
                    change_str = f"New #{last_rank}"
                    status = "New Ranking"
                elif last_rank > 100:
                    change_str = "Lost"
                    status = "Lost Ranking"
                else:
                    change = first_rank - last_rank
                    if change > 0:
                        change_str = f"↑{change}"
                        status = "Improved"
                    elif change < 0:
                        change_str = f"↓{abs(change)}"
                        status = "Declined"
                    else:
                        change_str = "0"
                        status = "No Change"
                
                # Truncate keyword if too long
                keyword_text = kw_data['keyword']
                if len(keyword_text) > 40:
                    keyword_text = keyword_text[:37] + "..."
                
                detail_data.append([
                    keyword_text,
                    first_rank_str,
                    last_rank_str,
                    change_str,
                    status
                ])
        
        if len(detail_data) > 1:  # Has data rows
            detail_table = Table(detail_data, colWidths=[3*inch, 1*inch, 1*inch, 1*inch, 1.5*inch])
            detail_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
            ]))
            
            elements.append(detail_table)
        
        # Build PDF
        try:
            doc.build(elements)
        except Exception as e:
            logger.error(f"Error building PDF: {e}")
            # Return a simple error PDF
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            elements = [Paragraph("Error generating report", styles['Title'])]
            doc.build(elements)
        
        # Get PDF content
        pdf_content = buffer.getvalue()
        buffer.close()
        
        return pdf_content
    
    def _create_ranking_chart(self):
        """Create a ranking trend chart for top keywords"""
        try:
            # Select top 10 keywords with most data
            keywords_with_data = []
            
            for kw_data in self.keywords_data[:20]:  # Check first 20 keywords
                keyword_id = kw_data['id']
                if keyword_id in self.ranking_data:
                    data_points = len([d for d in self.date_range if d in self.ranking_data[keyword_id]])
                    if data_points > 0:
                        keywords_with_data.append((keyword_id, kw_data['keyword'], data_points))
            
            # Sort by data points and take top 5
            keywords_with_data.sort(key=lambda x: x[2], reverse=True)
            top_keywords = keywords_with_data[:5]
            
            if not top_keywords:
                return None
            
            # Create drawing
            drawing = Drawing(400, 200)
            
            # Create line chart
            lc = HorizontalLineChart()
            lc.x = 50
            lc.y = 50
            lc.height = 125
            lc.width = 300
            
            # Prepare data
            data = []
            labels = []
            
            for keyword_id, keyword_text, _ in top_keywords:
                keyword_data = []
                for date_obj in self.date_range[::max(1, len(self.date_range)//10)]:  # Sample dates
                    if date_obj in self.ranking_data[keyword_id]:
                        # Invert rank for better visualization (lower rank = higher on chart)
                        rank = self.ranking_data[keyword_id][date_obj]['rank']
                        if rank > 100:
                            rank = 100
                        keyword_data.append(101 - rank)  # Invert so rank 1 appears at top
                    else:
                        keyword_data.append(0)
                
                if keyword_data:
                    data.append(keyword_data)
                    # Truncate label if needed
                    if len(keyword_text) > 20:
                        keyword_text = keyword_text[:17] + "..."
                    labels.append(keyword_text)
            
            if not data:
                return None
            
            lc.data = data
            lc.categoryAxis.categoryNames = [d.strftime('%m/%d') for d in self.date_range[::max(1, len(self.date_range)//10)]]
            
            # Style the chart
            lc.lines[0].strokeColor = colors.blue
            lc.lines[0].strokeWidth = 2
            
            if len(data) > 1:
                lc.lines[1].strokeColor = colors.green
                lc.lines[1].strokeWidth = 2
            
            if len(data) > 2:
                lc.lines[2].strokeColor = colors.red
                lc.lines[2].strokeWidth = 2
            
            if len(data) > 3:
                lc.lines[3].strokeColor = colors.orange
                lc.lines[3].strokeWidth = 2
            
            if len(data) > 4:
                lc.lines[4].strokeColor = colors.purple
                lc.lines[4].strokeWidth = 2
            
            lc.valueAxis.valueMin = 0
            lc.valueAxis.valueMax = 101
            lc.valueAxis.valueStep = 20
            
            drawing.add(lc)
            
            # Add legend
            from reportlab.graphics.charts.legends import Legend
            legend = Legend()
            legend.x = 360
            legend.y = 150
            legend.deltax = 75
            legend.deltay = 20
            legend.columnMaximum = 1
            legend.fontSize = 8
            
            # Set legend items
            legend.colorNamePairs = [
                (colors.blue, labels[0] if len(labels) > 0 else ''),
                (colors.green, labels[1] if len(labels) > 1 else ''),
                (colors.red, labels[2] if len(labels) > 2 else ''),
                (colors.orange, labels[3] if len(labels) > 3 else ''),
                (colors.purple, labels[4] if len(labels) > 4 else ''),
            ][:len(data)]
            
            drawing.add(legend)
            
            return drawing
            
        except Exception as e:
            logger.error(f"Error creating chart: {e}")
            return None