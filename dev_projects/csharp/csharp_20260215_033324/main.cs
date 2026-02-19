using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;

namespace CSharpAgent.JiraIntegration
{
    public class JiraService : IJiraService
    {
        private readonly string _jiraUrl;
        private readonly string _username;
        private readonly string _password;

        public JiraService(string jiraUrl, string username, string password)
        {
            _jiraUrl = jiraUrl;
            _username = username;
            _password = password;
        }

        public async Task CreateIssueAsync(string projectKey, string issueType, string summary, string description)
        {
            var client = new JiraClient(_jiraUrl, _username, _password);
            var issue = new Issue
            {
                Project = new Project { Key = projectKey },
                Type = new IssueType { Name = issueType },
                Summary = summary,
                Description = description
            };

            await client.CreateIssueAsync(issue);
        }

        public async Task UpdateIssueAsync(string issueId, string summary, string description)
        {
            var client = new JiraClient(_jiraUrl, _username, _password);
            var issue = new Issue
            {
                Id = issueId,
                Summary = summary,
                Description = description
            };

            await client.UpdateIssueAsync(issue);
        }

        public async Task DeleteIssueAsync(string issueId)
        {
            var client = new JiraClient(_jiraUrl, _username, _password);
            await client.DeleteIssueAsync(issueId);
        }
    }
}