using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;
using Xunit;

namespace YourNamespace.Tests
{
    public class ProgramTests
    {
        [Fact]
        public async Task TestGetIssuesAsync_Success()
        {
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            try
            {
                var issues = await jiraClient.GetIssuesAsync();

                Assert.NotEmpty(issues);
                foreach (var issue in issues)
                {
                    Assert.NotNull(issue.Key);
                    Assert.NotNull(issue.Fields.Summary);
                }
            }
            catch (Exception ex)
            {
                throw new Exception("Test failed", ex);
            }
        }

        [Fact]
        public async Task TestGetIssuesAsync_Error()
        {
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            try
            {
                await jiraClient.GetIssuesAsync();
            }
            catch (Exception ex)
            {
                Assert.IsType<HttpRequestException>(ex);
                Console.WriteLine($"Error: {ex.Message}");
            }
        }

        [Fact]
        public async Task TestGetIssuesAsync_InvalidCredentials()
        {
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "invalid-username", "invalid-password");

            try
            {
                await jiraClient.GetIssuesAsync();
            }
            catch (Exception ex)
            {
                Assert.IsType<HttpRequestException>(ex);
                Console.WriteLine($"Error: {ex.Message}");
            }
        }

        [Fact]
        public async Task TestGetIssuesAsync_InvalidUrl()
        {
            var jiraClient = new JiraClient("https://invalid-url.atlassian.net", "your-username", "your-password");

            try
            {
                await jiraClient.GetIssuesAsync();
            }
            catch (Exception ex)
            {
                Assert.IsType<HttpRequestException>(ex);
                Console.WriteLine($"Error: {ex.Message}");
            }
        }

        [Fact]
        public async Task TestGetIssuesAsync_NullCredentials()
        {
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", null, null);

            try
            {
                await jiraClient.GetIssuesAsync();
            }
            catch (Exception ex)
            {
                Assert.IsType<HttpRequestException>(ex);
                Console.WriteLine($"Error: {ex.Message}");
            }
        }

        [Fact]
        public async Task TestGetIssuesAsync_NullUrl()
        {
            var jiraClient = new JiraClient(null, "your-username", "your-password");

            try
            {
                await jiraClient.GetIssuesAsync();
            }
            catch (Exception ex)
            {
                Assert.IsType<HttpRequestException>(ex);
                Console.WriteLine($"Error: {ex.Message}");
            }
        }

        [Fact]
        public async Task TestGetIssuesAsync_NullCredentialsAndUrl()
        {
            var jiraClient = new JiraClient(null, null, null);

            try
            {
                await jiraClient.GetIssuesAsync();
            }
            catch (Exception ex)
            {
                Assert.IsType<HttpRequestException>(ex);
                Console.WriteLine($"Error: {ex.Message}");
            }
        }
    }
}