using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;

namespace CSharpAgent.JiraIntegration
{
    public class JiraClient
    {
        private readonly JiraClientOptions _options;

        public JiraClient(JiraClientOptions options)
        {
            _options = options;
        }

        public async Task CreateIssueAsync(string issueKey, string summary, string description)
        {
            var client = new JiraSharp.Client.JiraSharpClient(_options);
            var issue = new JiraSharp.Model.Issue
            {
                Key = issueKey,
                Summary = summary,
                Description = description
            };

            await client.CreateIssueAsync(issue);
        }

        public async Task UpdateIssueAsync(string issueKey, string summary, string description)
        {
            var client = new JiraSharp.Client.JiraSharpClient(_options);
            var issue = new JiraSharp.Model.Issue
            {
                Key = issueKey,
                Summary = summary,
                Description = description
            };

            await client.UpdateIssueAsync(issue);
        }

        public async Task DeleteIssueAsync(string issueKey)
        {
            var client = new JiraSharp.Client.JiraSharpClient(_options);
            await client.DeleteIssueAsync(issueKey);
        }
    }

    public class JiraClientOptions
    {
        public string Url { get; set; }
        public string Username { get; set; }
        public string Password { get; set; }
    }
}