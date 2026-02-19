using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;
using Xunit;

namespace JiraSharp.Tests
{
    public class ProgramTests
    {
        [Fact]
        public async Task CreateProjectTest()
        {
            var client = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

            var project = await client.Projects.CreateAsync(new ProjectCreateRequest()
            {
                Key = "TEST",
                Name = "Test Project",
                Description = "This is a test project for integration with Jira."
            });

            Assert.NotNull(project);
        }

        [Fact]
        public async Task CreateIssueTest()
        {
            var client = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

            var issue = await client.Issues.CreateAsync(new IssueCreateRequest()
            {
                Key = "TEST-1",
                ProjectId = 12345, // Replace with actual project ID
                Summary = "Test Task",
                Description = "This is a test task for integration with Jira."
            });

            Assert.NotNull(issue);
        }

        [Fact]
        public async Task MonitorTaskStatusTest()
        {
            var client = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

            var issue = await client.Issues.GetAsync(12345); // Replace with actual issue ID

            while (true)
            {
                var issueStatus = await client.Issues.GetAsync(issue.Id);
                Console.WriteLine($"Issue status: {issueStatus.Fields.Status.Name}");

                if (issueStatus.Fields.Status.Name == "Done")
                {
                    Console.WriteLine("Task completed!");
                    break;
                }

                await Task.Delay(1000); // Esperar 1 segundo antes de verificar novamente
            }
        }
    }
}