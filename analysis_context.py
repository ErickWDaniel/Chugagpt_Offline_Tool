import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

class AnalysisContextManager:
    """Manages analysis context for chat sessions."""
    
    def __init__(self, context_file: str = "analysis_context.json"):
        self.context_file = context_file
        self.current_context = None
        self.context_summary = None
        
    def save_analysis_context(self, analysis_results: Dict[str, Any], project_path: str):
        """Save analysis results as context for future chat sessions."""
        context_data = {
            'timestamp': datetime.now().isoformat(),
            'project_path': project_path,
            'project_name': Path(project_path).name,
            'summary': analysis_results['summary'],
            'architecture': analysis_results['architecture'],
            'issues': analysis_results['issues'],
            'suggestions': analysis_results['suggestions'],
            'file_feedback': analysis_results['file_feedback'],
            'key_files': self._extract_key_files(analysis_results),
            'context_prompt': self._create_context_prompt(analysis_results, project_path)
        }
        
        try:
            with open(self.context_file, 'w', encoding='utf-8') as f:
                json.dump(context_data, f, indent=2, ensure_ascii=False)
            
            self.current_context = context_data
            self.context_summary = self._create_context_summary(context_data)
            print(f"Analysis context saved for project: {context_data['project_name']}")
            
        except Exception as e:
            print(f"Error saving analysis context: {e}")
    
    def load_analysis_context(self) -> Optional[Dict[str, Any]]:
        """Load the most recent analysis context."""
        if not os.path.exists(self.context_file):
            return None
            
        try:
            with open(self.context_file, 'r', encoding='utf-8') as f:
                self.current_context = json.load(f)
                self.context_summary = self._create_context_summary(self.current_context)
                return self.current_context
        except Exception as e:
            print(f"Error loading analysis context: {e}")
            return None
    
    def get_context_for_chat(self, max_length: int = 2000) -> Optional[str]:
        """Get formatted context for chat prompts."""
        if not self.current_context:
            return None
            
        context = self.current_context.get('context_prompt', '')
        if len(context) > max_length:
            # Truncate but keep essential information
            context = context[:max_length-100] + "\n\n[Context truncated for length...]"
        
        return context
    
    def get_context_summary(self) -> Optional[str]:
        """Get a brief summary of the current analysis context."""
        return self.context_summary
    
    def has_context(self) -> bool:
        """Check if analysis context is available."""
        return self.current_context is not None
    
    def clear_context(self):
        """Clear the current analysis context."""
        if os.path.exists(self.context_file):
            os.remove(self.context_file)
        self.current_context = None
        self.context_summary = None
    
    def _extract_key_files(self, analysis_results: Dict[str, Any]) -> Dict[str, Any]:
        """Extract key files information for quick reference."""
        file_analysis = analysis_results.get('file_analysis', {})
        key_files = {}
        
        for file_path, info in file_analysis.items():
            if info.get('type') == 'Python':
                key_files[file_path] = {
                    'type': info.get('type'),
                    'classes': len(info.get('classes', [])),
                    'functions': len(info.get('functions', [])),
                    'lines': info.get('line_count', 0),
                    'complexity': info.get('complexity', 0)
                }
        
        return key_files
    
    def _create_context_prompt(self, analysis_results: Dict[str, Any], project_path: str) -> str:
        """Create a comprehensive context prompt for chat."""
        summary = analysis_results.get('summary', {})
        architecture = analysis_results.get('architecture', {})
        issues = analysis_results.get('issues', {})
        
        context = f"""# Project Analysis Context

## Project: {Path(project_path).name}
- **Location**: {project_path}
- **Total Files**: {summary.get('total_files', 0)}
- **Lines of Code**: {summary.get('total_lines', 0)}
- **Languages**: {', '.join([f'{lang}: {count}' for lang, count in summary.get('languages', {}).items()])}
- **Issues Found**: {summary.get('issues_count', 0)}

## Architecture Overview
"""
        
        if architecture.get('main_modules'):
            context += f"- **Main Modules**: {', '.join(architecture['main_modules'][:3])}\n"
        if architecture.get('utils_modules'):
            context += f"- **Utility Modules**: {', '.join(architecture['utils_modules'][:3])}\n"
        if architecture.get('test_files'):
            context += f"- **Test Files**: {len(architecture['test_files'])}\n"
        
        context += "\n## Key Issues\n"
        for category, issue_list in issues.items():
            if issue_list:
                context += f"### {category.replace('_', ' ').title()}\n"
                for issue in issue_list[:3]:  # Limit to 3 per category
                    context += f"- {issue}\n"
        
        context += "\n## Available Files\n"
        file_analysis = analysis_results.get('file_analysis', {})
        for file_path, info in list(file_analysis.items())[:10]:  # First 10 files
            if info.get('type') == 'Python':
                context += f"- **{file_path}**: {info.get('line_count', 0)} lines, {len(info.get('classes', []))} classes, {len(info.get('functions', []))} functions\n"
        
        context += "\n## Usage Notes\n"
        context += "- I have analyzed this codebase and can provide insights about its structure, issues, and improvements\n"
        context += "- Ask me about specific files, functions, or architectural decisions\n"
        context += "- I can suggest refactoring approaches or explain complex code sections\n"
        
        return context
    
    def _create_context_summary(self, context_data: Dict[str, Any]) -> str:
        """Create a brief summary of the analysis context."""
        summary = context_data.get('summary', {})
        return f"Analyzed project '{context_data.get('project_name', 'Unknown')}' with {summary.get('total_files', 0)} files, {summary.get('issues_count', 0)} issues found. Ready to discuss codebase architecture and improvements."

# Global context manager instance
context_manager = AnalysisContextManager()
