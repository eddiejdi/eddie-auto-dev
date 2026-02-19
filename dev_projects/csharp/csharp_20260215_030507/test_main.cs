using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;
using JiraSharp.Model;
using Xunit;

namespace CSharpAgent.Tests
{
    public class ProgramTests
    {
        [Fact]
        public async Task TestGetProjectAsync()
        {
            var client = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");
            var projectKey = "PROJECT_KEY";

            try
            {
                var project = await client.Projects.GetProjectAsync(projectKey);
                Assert.NotNull(project);
                Console.WriteLine($"Project ID: {project.Id}, Name: {project.Name}");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error getting project: {ex.Message}");
            }
        }

        [Fact]
        public async Task TestGetIssuesAsync()
        {
            var client = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");
            var projectId = "PROJECT_ID";

            try
            {
                var issues = await client.Issues.GetAllIssuesAsync(projectId);
                Assert.NotNull(issues);
                foreach (var issue in issues)
                {
                    Console.WriteLine($"Issue ID: {issue.Key}, Summary: {issue.Summary}");
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error getting issues: {ex.Message}");
            }
        }

        // Add more test cases as needed
    }
}