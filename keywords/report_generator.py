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
        self.report_type = report.report_type
        self.start_date = report.start_date
        self.end_date = report.end_date
        
        # Calculate date range (list of dates) - only for keyword_rankings
        if self.report_type == 'keyword_rankings' and self.start_date and self.end_date:
            self.date_range = self._generate_date_range()
        else:
            self.date_range = []
        
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
            # Route to appropriate generator based on report type
            if self.report_type == 'keyword_rankings':
                return self._generate_keyword_rankings_report()
            elif self.report_type == 'page_rankings':
                return self._generate_page_rankings_report()
            elif self.report_type == 'top_competitors':
                return self._generate_top_competitors_report()
            elif self.report_type == 'competitors_targets':
                return self._generate_competitors_targets_report()
            else:
                raise ValueError(f"Unknown report type: {self.report_type}")
            
        except Exception as e:
            logger.error(f"Error generating report: {e}", exc_info=True)
            results['error'] = str(e)
            return results
    
    def _generate_keyword_rankings_report(self) -> Dict[str, Any]:
        """Generate traditional keyword rankings report"""
        results = {
            'success': False,
            'csv_path': None,
            'pdf_path': None,
            'error': None
        }
        
        try:
            # Load and process data
            logger.info(f"Loading data for keyword rankings report {self.report.id}")
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
            logger.error(f"Error generating keyword rankings report: {e}", exc_info=True)
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
        
        # Don't fill missing ranks - show NR for missing data
        logger.info(f"Loaded ranking data for {len(self.ranking_data)} keywords")
    
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
                f"GOOGLE, {kw_data['country']}",  # Use full country name instead of country_code
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
    
    def _generate_page_rankings_report(self) -> Dict[str, Any]:
        """Generate page rankings report showing which pages rank for most keywords"""
        results = {
            'success': False,
            'csv_path': None,
            'pdf_path': None,
            'error': None
        }
        
        try:
            logger.info(f"Generating page rankings report for project {self.project.id}")
            from .models import Keyword
            from collections import defaultdict
            from urllib.parse import urlparse
            
            # Get all active keywords for the project
            keywords = Keyword.objects.filter(
                project=self.project,
                archive=False
            ).exclude(rank=0).exclude(rank__gt=100)
            
            # Apply keyword filters if set
            if self.report.keywords.exists():
                keywords = self.report.keywords.filter(archive=False)
            
            # Group keywords by ranking URL
            page_data = defaultdict(lambda: {
                'keywords': [],
                'total_count': 0,
                'avg_position': 0,
                'top_3': 0,
                'top_10': 0,
                'top_30': 0
            })
            
            for keyword in keywords:
                if keyword.rank_url:
                    # Normalize URL (remove query params for grouping)
                    parsed_url = urlparse(keyword.rank_url)
                    clean_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
                    
                    page_data[clean_url]['keywords'].append({
                        'keyword': keyword.keyword,
                        'rank': keyword.rank,
                        'country': keyword.country  # Include country information
                    })
                    page_data[clean_url]['total_count'] += 1
                    
                    if keyword.rank <= 3:
                        page_data[clean_url]['top_3'] += 1
                    if keyword.rank <= 10:
                        page_data[clean_url]['top_10'] += 1
                    if keyword.rank <= 30:
                        page_data[clean_url]['top_30'] += 1
            
            # Calculate average positions
            for url, data in page_data.items():
                if data['keywords']:
                    total_rank = sum(k['rank'] for k in data['keywords'])
                    data['avg_position'] = round(total_rank / len(data['keywords']), 1)
            
            # Sort by total keywords (descending)
            sorted_pages = sorted(page_data.items(), key=lambda x: x[1]['total_count'], reverse=True)
            
            # Generate CSV if requested
            if self.report.report_format in ['csv', 'both']:
                csv_buffer = io.StringIO()
                csv_writer = csv.writer(csv_buffer)
                
                # Write headers
                csv_writer.writerow([
                    'Page URL',
                    'Total Keywords',
                    'Avg. Position',
                    'Top 3',
                    'Top 10',
                    'Top 30',
                    'Keywords with Country (Top 10)'
                ])
                
                # Write data
                for url, data in sorted_pages:
                    # Get top 10 keywords for this page with country information
                    top_keywords = sorted(data['keywords'], key=lambda x: x['rank'])[:10]
                    keywords_str = '; '.join([f"{k['keyword']} - {k['country']} (#{k['rank']})" for k in top_keywords])
                    
                    csv_writer.writerow([
                        url,
                        data['total_count'],
                        data['avg_position'],
                        data['top_3'],
                        data['top_10'],
                        data['top_30'],
                        keywords_str
                    ])
                
                csv_content = csv_buffer.getvalue()
                results['csv_content'] = csv_content
                results['csv_size'] = len(csv_content)
            
            # Generate PDF if requested
            if self.report.report_format in ['pdf', 'both']:
                pdf_buffer = io.BytesIO()
                doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
                story = []
                styles = getSampleStyleSheet()
                
                # Title
                title_style = ParagraphStyle(
                    'CustomTitle',
                    parent=styles['Heading1'],
                    fontSize=24,
                    textColor=colors.HexColor('#1e40af'),
                    spaceAfter=30,
                    alignment=TA_CENTER
                )
                story.append(Paragraph(f"Page Rankings Report", title_style))
                story.append(Paragraph(f"{self.project.domain}", styles['Heading2']))
                story.append(Spacer(1, 0.5*inch))
                
                # Summary stats
                story.append(Paragraph("Summary", styles['Heading2']))
                summary_data = [
                    ['Metric', 'Value'],
                    ['Total Pages Ranking', len(sorted_pages)],
                    ['Total Keywords', sum(d['total_count'] for _, d in sorted_pages)],
                    ['Average Keywords per Page', round(sum(d['total_count'] for _, d in sorted_pages) / max(len(sorted_pages), 1), 1)]
                ]
                summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
                summary_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 12),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ]))
                story.append(summary_table)
                story.append(Spacer(1, 0.5*inch))
                
                # Top pages table
                story.append(Paragraph("Top Ranking Pages", styles['Heading2']))
                table_data = [['Page URL', 'Keywords', 'Avg Pos', 'Top 3', 'Top 10']]
                
                for url, data in sorted_pages[:20]:  # Top 20 pages
                    # Truncate URL for display
                    display_url = url[:50] + '...' if len(url) > 50 else url
                    table_data.append([
                        display_url,
                        str(data['total_count']),
                        str(data['avg_position']),
                        str(data['top_3']),
                        str(data['top_10'])
                    ])
                
                pages_table = Table(table_data, colWidths=[3.5*inch, 1*inch, 1*inch, 0.75*inch, 0.75*inch])
                pages_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ]))
                story.append(pages_table)
                
                # Build PDF
                doc.build(story)
                pdf_content = pdf_buffer.getvalue()
                results['pdf_content'] = pdf_content
                results['pdf_size'] = len(pdf_content)
            
            results['success'] = True
            results['summary'] = {
                'total_pages': len(sorted_pages),
                'total_keywords': sum(d['total_count'] for _, d in sorted_pages),
                'top_page': sorted_pages[0][0] if sorted_pages else None
            }
            
        except Exception as e:
            logger.error(f"Error generating page rankings report: {e}", exc_info=True)
            results['error'] = str(e)
        
        return results
    
    def _generate_top_competitors_report(self) -> Dict[str, Any]:
        """Generate top competitors report based on competitor tracking data"""
        results = {
            'success': False,
            'csv_path': None,
            'pdf_path': None,
            'error': None
        }
        
        try:
            logger.info(f"Generating top competitors report for project {self.project.id}")
            from competitors.models import Target, TargetKeywordRank
            from collections import defaultdict
            
            # Get all competitors (targets) for this project
            competitors = Target.objects.filter(project=self.project)
            
            competitor_stats = []
            
            for competitor in competitors:
                # Get latest ranking data for this competitor (target)
                # Use a simpler approach without distinct to avoid PostgreSQL issues
                from django.db.models import Max
                latest_ranks = TargetKeywordRank.objects.filter(
                    target=competitor
                ).select_related('keyword')
                
                # Calculate stats
                total_keywords = latest_ranks.count()
                top_3 = latest_ranks.filter(rank__lte=3).count()
                top_10 = latest_ranks.filter(rank__lte=10).count()
                top_30 = latest_ranks.filter(rank__lte=30).count()
                
                avg_rank = 0
                if total_keywords > 0:
                    ranks = [r.rank for r in latest_ranks if r.rank > 0 and r.rank <= 100]
                    avg_rank = round(sum(ranks) / len(ranks), 1) if ranks else 0
                
                competitor_stats.append({
                    'domain': competitor.domain,
                    'total_keywords': total_keywords,
                    'avg_rank': avg_rank,
                    'top_3': top_3,
                    'top_10': top_10,
                    'top_30': top_30,
                    'visibility_score': top_3 * 3 + top_10 * 2 + top_30  # Simple visibility scoring
                })
            
            # Sort by visibility score
            competitor_stats.sort(key=lambda x: x['visibility_score'], reverse=True)
            
            # Generate CSV if requested
            if self.report.report_format in ['csv', 'both']:
                csv_buffer = io.StringIO()
                csv_writer = csv.writer(csv_buffer)
                
                # Write headers
                csv_writer.writerow([
                    'Competitor Domain',
                    'Total Keywords',
                    'Avg. Position',
                    'Top 3',
                    'Top 10',
                    'Top 30',
                    'Visibility Score'
                ])
                
                # Write data
                for comp in competitor_stats:
                    csv_writer.writerow([
                        comp['domain'],
                        comp['total_keywords'],
                        comp['avg_rank'],
                        comp['top_3'],
                        comp['top_10'],
                        comp['top_30'],
                        comp['visibility_score']
                    ])
                
                csv_content = csv_buffer.getvalue()
                results['csv_content'] = csv_content
                results['csv_size'] = len(csv_content)
            
            # Generate PDF if requested
            if self.report.report_format in ['pdf', 'both']:
                pdf_buffer = io.BytesIO()
                doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
                story = []
                styles = getSampleStyleSheet()
                
                # Title
                title_style = ParagraphStyle(
                    'CustomTitle',
                    parent=styles['Heading1'],
                    fontSize=24,
                    textColor=colors.HexColor('#1e40af'),
                    spaceAfter=30,
                    alignment=TA_CENTER
                )
                story.append(Paragraph(f"Top Competitors Report", title_style))
                story.append(Paragraph(f"{self.project.domain}", styles['Heading2']))
                story.append(Spacer(1, 0.5*inch))
                
                # Competitors table
                table_data = [['Competitor', 'Keywords', 'Avg Pos', 'Top 3', 'Top 10', 'Top 30', 'Score']]
                
                for comp in competitor_stats[:20]:  # Top 20 competitors
                    table_data.append([
                        comp['domain'][:30] + '...' if len(comp['domain']) > 30 else comp['domain'],
                        str(comp['total_keywords']),
                        str(comp['avg_rank']),
                        str(comp['top_3']),
                        str(comp['top_10']),
                        str(comp['top_30']),
                        str(comp['visibility_score'])
                    ])
                
                comp_table = Table(table_data, colWidths=[2.5*inch, 0.9*inch, 0.9*inch, 0.7*inch, 0.7*inch, 0.7*inch, 0.8*inch])
                comp_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ]))
                story.append(comp_table)
                
                # Build PDF
                doc.build(story)
                pdf_content = pdf_buffer.getvalue()
                results['pdf_content'] = pdf_content
                results['pdf_size'] = len(pdf_content)
            
            results['success'] = True
            results['summary'] = {
                'total_competitors': len(competitor_stats),
                'top_competitor': competitor_stats[0]['domain'] if competitor_stats else None
            }
            
        except Exception as e:
            logger.error(f"Error generating top competitors report: {e}", exc_info=True)
            results['error'] = str(e)
        
        return results
    
    def _generate_competitors_targets_report(self) -> Dict[str, Any]:
        """Generate competitors targets report showing what keywords competitors target"""
        results = {
            'success': False,
            'csv_path': None,
            'pdf_path': None,
            'error': None
        }
        
        try:
            logger.info(f"Generating competitors targets report for project {self.project.id}")
            from competitors.models import TargetKeywordRank
            from collections import defaultdict
            
            # Get all competitor keywords (target keyword ranks) for this project
            comp_keywords = TargetKeywordRank.objects.filter(
                target__project=self.project
            ).select_related('target', 'keyword')
            
            # Group by keyword
            keyword_competitors = defaultdict(list)
            
            for ck in comp_keywords:
                # Create a key that includes both keyword and country
                keyword_key = f"{ck.keyword.keyword}|{ck.keyword.country}"
                keyword_competitors[keyword_key].append({
                    'competitor': ck.target.domain,
                    'rank': ck.rank if ck.rank > 0 else 101,
                    'url': ck.rank_url,
                    'country': ck.keyword.country
                })
            
            # Sort keywords by number of competitors targeting them
            keyword_data = []
            for keyword_key, competitors in keyword_competitors.items():
                # Split the key to get keyword and country
                keyword_parts = keyword_key.split('|')
                keyword = keyword_parts[0]
                country = keyword_parts[1] if len(keyword_parts) > 1 else 'US'
                
                # Sort competitors by rank
                competitors.sort(key=lambda x: x['rank'])
                
                keyword_data.append({
                    'keyword': keyword,
                    'country': country,
                    'competitor_count': len(competitors),
                    'top_competitor': competitors[0]['competitor'] if competitors else None,
                    'top_rank': competitors[0]['rank'] if competitors else 0,
                    'competitors': competitors[:5]  # Top 5 competitors for this keyword
                })
            
            # Sort by competitor count
            keyword_data.sort(key=lambda x: x['competitor_count'], reverse=True)
            
            # Generate CSV if requested
            if self.report.report_format in ['csv', 'both']:
                csv_buffer = io.StringIO()
                csv_writer = csv.writer(csv_buffer)
                
                # Write headers
                csv_writer.writerow([
                    'Keyword',
                    'Country',
                    'Competitors Count',
                    'Top Competitor',
                    'Top Rank',
                    'All Competitors (Top 5)'
                ])
                
                # Write data
                for kw_data in keyword_data:
                    competitors_str = '; '.join([
                        f"{c['competitor']} (#{c['rank']})"
                        for c in kw_data['competitors']
                    ])
                    
                    csv_writer.writerow([
                        kw_data['keyword'],
                        kw_data['country'],
                        kw_data['competitor_count'],
                        kw_data['top_competitor'],
                        kw_data['top_rank'] if kw_data['top_rank'] <= 100 else 'NR',
                        competitors_str
                    ])
                
                csv_content = csv_buffer.getvalue()
                results['csv_content'] = csv_content
                results['csv_size'] = len(csv_content)
            
            # Generate PDF if requested
            if self.report.report_format in ['pdf', 'both']:
                pdf_buffer = io.BytesIO()
                doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
                story = []
                styles = getSampleStyleSheet()
                
                # Title
                title_style = ParagraphStyle(
                    'CustomTitle',
                    parent=styles['Heading1'],
                    fontSize=24,
                    textColor=colors.HexColor('#1e40af'),
                    spaceAfter=30,
                    alignment=TA_CENTER
                )
                story.append(Paragraph(f"Competitor Targets Report", title_style))
                story.append(Paragraph(f"{self.project.domain}", styles['Heading2']))
                story.append(Spacer(1, 0.5*inch))
                
                # Keywords table
                table_data = [['Keyword', 'Country', 'Competitors', 'Top Competitor', 'Top Rank']]
                
                for kw_data in keyword_data[:50]:  # Top 50 keywords
                    keyword_display = kw_data['keyword'][:30] + '...' if len(kw_data['keyword']) > 30 else kw_data['keyword']
                    comp_display = kw_data['top_competitor'][:25] + '...' if kw_data['top_competitor'] and len(kw_data['top_competitor']) > 25 else kw_data['top_competitor']
                    
                    table_data.append([
                        keyword_display,
                        kw_data['country'],
                        str(kw_data['competitor_count']),
                        comp_display or 'N/A',
                        str(kw_data['top_rank']) if kw_data['top_rank'] <= 100 else 'NR'
                    ])
                
                kw_table = Table(table_data, colWidths=[2.5*inch, 0.8*inch, 1*inch, 2.2*inch, 0.8*inch])
                kw_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ]))
                story.append(kw_table)
                
                # Build PDF
                doc.build(story)
                pdf_content = pdf_buffer.getvalue()
                results['pdf_content'] = pdf_content
                results['pdf_size'] = len(pdf_content)
            
            results['success'] = True
            results['summary'] = {
                'total_keywords': len(keyword_data),
                'most_competitive': keyword_data[0]['keyword'] if keyword_data else None
            }
            
        except Exception as e:
            logger.error(f"Error generating competitors targets report: {e}", exc_info=True)
            results['error'] = str(e)
        
        return results