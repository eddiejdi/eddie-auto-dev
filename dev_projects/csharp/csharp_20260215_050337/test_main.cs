using System;
using System.Threading.Tasks;
using Xunit;

namespace CSharpAgent.JiraIntegration.Tests
{
    public class JiraClientTests
    {
        [Fact]
        public async Task CreateIssueAsync_Success()
        {
            var options = new JiraClientOptions
            {
                Url = "http://example.com",
                Username = "user",
                Password = "pass"
            };

            var client = new JiraClient(options);
            var issueKey = "TEST-1";
            var summary = "Test Issue";
            var description = "This is a test issue.";

            await client.CreateIssueAsync(issueKey, summary, description);

            // Add assertions here to verify the issue was created successfully
        }

        [Fact]
        public async Task CreateIssueAsync_Error()
        {
            var options = new JiraClientOptions
            {
                Url = "http://example.com",
                Username = "user",
                Password = "pass"
            };

            var client = new JiraClient(options);
            var issueKey = "TEST-1";
            var summary = "";
            var description = "";

            await Assert.ThrowsAsync<Exception>(async () => await client.CreateIssueAsync(issueKey, summary, description));
        }

        // Add more test cases as needed
    }
}