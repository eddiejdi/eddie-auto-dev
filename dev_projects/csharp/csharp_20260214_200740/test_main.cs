using System;
using System.Collections.Generic;
using System.Linq;

class JiraIntegrationTests
{
    [Fact]
    public void ConnectToJira_WithValidCredentials_ShouldReturnSuccess()
    {
        // Arrange
        var url = "https://jira.example.com";
        var username = "admin";
        var password = "password";

        // Act
        bool result = JiraIntegration.ConnectToJira(url, username, password);

        // Assert
        Assert.True(result);
    }

    [Fact]
    public void ConnectToJira_WithInvalidCredentials_ShouldReturnFailure()
    {
        // Arrange
        var url = "https://jira.example.com";
        var username = "admin";
        var password = "wrongpassword";

        // Act
        bool result = JiraIntegration.ConnectToJira(url, username, password);

        // Assert
        Assert.False(result);
    }

    [Fact]
    public void CreateTicket_WithValidData_ShouldReturnSuccess()
    {
        // Arrange
        string title = "Test Ticket";
        string description = "This is a test ticket.";
        string projectKey = "SCRUM-14";

        // Act
        bool result = JiraIntegration.CreateTicket(title, description, projectKey);

        // Assert
        Assert.True(result);
    }

    [Fact]
    public void CreateTicket_WithInvalidData_ShouldReturnFailure()
    {
        // Arrange
        string title = "";
        string description = "This is a test ticket.";
        string projectKey = "SCRUM-14";

        // Act
        bool result = JiraIntegration.CreateTicket(title, description, projectKey);

        // Assert
        Assert.False(result);
    }

    [Fact]
    public void SearchTickets_WithValidKeyword_ShouldReturnSuccess()
    {
        // Arrange
        string keyword = "Test Ticket";

        // Act
        List<Ticket> tickets = JiraIntegration.SearchTickets(keyword);

        // Assert
        Assert.NotEmpty(tickets);
    }

    [Fact]
    public void SearchTickets_WithInvalidKeyword_ShouldReturnFailure()
    {
        // Arrange
        string keyword = "";

        // Act
        List<Ticket> tickets = JiraIntegration.SearchTickets(keyword);

        // Assert
        Assert.Empty(tickets);
    }

    [Fact]
    public void UpdateTicket_WithValidData_ShouldReturnSuccess()
    {
        // Arrange
        int ticketId = 1;
        string title = "Updated Test Ticket";
        string description = "This is an updated test ticket.";

        // Act
        bool result = JiraIntegration.UpdateTicket(ticketId, title, description);

        // Assert
        Assert.True(result);
    }

    [Fact]
    public void UpdateTicket_WithInvalidData_ShouldReturnFailure()
    {
        // Arrange
        int ticketId = 1;
        string title = "";
        string description = "This is an updated test ticket.";

        // Act
        bool result = JiraIntegration.UpdateTicket(ticketId, title, description);

        // Assert
        Assert.False(result);
    }

    [Fact]
    public void DeleteTicket_WithValidData_ShouldReturnSuccess()
    {
        // Arrange
        int ticketId = 1;

        // Act
        bool result = JiraIntegration.DeleteTicket(ticketId);

        // Assert
        Assert.True(result);
    }

    [Fact]
    public void DeleteTicket_WithInvalidData_ShouldReturnFailure()
    {
        // Arrange
        int ticketId = -1;

        // Act
        bool result = JiraIntegration.DeleteTicket(ticketId);

        // Assert
        Assert.False(result);
    }
}