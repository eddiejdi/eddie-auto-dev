using System;
using System.Threading.Tasks;
using JiraSharp.Client;
using Microsoft.VisualStudio.TestTools.UnitTesting;

namespace CSharpAgentJiraIntegration.Tests
{
    [TestClass]
    public class ProgramTests
    {
        [TestMethod]
        public async Task TestCreateIssueWithValidData()
        {
            // Initialize Jira client with your credentials
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            // Create a new issue
            var issue = new Issue
            {
                Summary = "New Task",
                Description = "This is a new task created by the C# Agent.",
                ProjectKey = "YOUR_PROJECT_KEY"
            };

            // Create the issue in Jira
            await jiraClient.CreateIssueAsync(issue);

            Console.WriteLine("Issue created successfully.");
        }

        [TestMethod]
        public async Task TestCreateIssueWithInvalidData()
        {
            // Initialize Jira client with your credentials
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            // Create a new issue with invalid data
            var issue = new Issue
            {
                Summary = "",
                Description = null,
                ProjectKey = "INVALID_PROJECT_KEY"
            };

            try
            {
                await jiraClient.CreateIssueAsync(issue);
                Assert.Fail("Expected an exception to be thrown.");
            }
            catch (Exception ex)
            {
                // Check if the exception is as expected
                Assert.IsInstanceOfType(ex, typeof(ArgumentException));
            }
        }

        [TestMethod]
        public async Task TestCreateIssueWithNullData()
        {
            // Initialize Jira client with your credentials
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            // Create a new issue with null data
            var issue = new Issue
            {
                Summary = null,
                Description = null,
                ProjectKey = null
            };

            try
            {
                await jiraClient.CreateIssueAsync(issue);
                Assert.Fail("Expected an exception to be thrown.");
            }
            catch (Exception ex)
            {
                // Check if the exception is as expected
                Assert.IsInstanceOfType(ex, typeof(ArgumentException));
            }
        }
    }
}