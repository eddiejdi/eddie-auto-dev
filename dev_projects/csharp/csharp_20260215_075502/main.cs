using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;
using JiraSharp.Model;

namespace CSharpAgent.JiraIntegration
{
    public class JiraService
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

        public async Task CreateIssueAsync(Issue issue)
        {
            var client = new JiraClient(_jiraUrl);
            await client.AuthenticateAsync(_username, _password);

            var project = await client.Projects.GetProjectAsync(issue.ProjectKey);
            var issueType = await client.IssueTypes.GetIssueTypeAsync(project.IssueTypeId);

            var createIssueRequest = new CreateIssueRequest
            {
                Fields = new IssueFields
                {
                    Project = new ProjectField { Key = project.Key },
                    Summary = issue.Summary,
                    Description = issue.Description,
                    Priority = new PriorityField { Id = issue.PriorityId },
                    Status = new StatusField { Id = issue.StatusId }
                }
            };

            var createdIssue = await client.Issue.CreateAsync(createIssueRequest);
        }

        public async Task UpdateIssueAsync(Issue issue)
        {
            var client = new JiraClient(_jiraUrl);
            await client.AuthenticateAsync(_username, _password);

            var project = await client.Projects.GetProjectAsync(issue.ProjectKey);
            var issueType = await client.IssueTypes.GetIssueTypeAsync(project.IssueTypeId);

            var updateIssueRequest = new UpdateIssueRequest
            {
                Fields = new IssueFields
                {
                    Summary = issue.Summary,
                    Description = issue.Description,
                    Priority = new PriorityField { Id = issue.PriorityId },
                    Status = new StatusField { Id = issue.StatusId }
                }
            };

            await client.Issue.UpdateAsync(issue.Id, updateIssueRequest);
        }

        public async Task DeleteIssueAsync(string issueKey)
        {
            var client = new JiraClient(_jiraUrl);
            await client.AuthenticateAsync(_username, _password);

            await client.Issue.DeleteAsync(issueKey);
        }
    }
}