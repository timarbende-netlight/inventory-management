"""
Tests for reports API endpoints (quarterly performance and monthly trends).
"""
import pytest


class TestQuarterlyReportsEndpoint:
    """Test suite for /api/reports/quarterly."""

    def test_get_quarterly_reports(self, client):
        """Test getting quarterly reports without filters."""
        response = client.get("/api/reports/quarterly")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        for quarter in data:
            assert "quarter" in quarter
            assert "total_orders" in quarter
            assert "total_revenue" in quarter
            assert "delivered_orders" in quarter
            assert "avg_order_value" in quarter
            assert "fulfillment_rate" in quarter

    def test_quarterly_reports_sorted(self, client):
        """Test that quarters are returned in chronological order."""
        data = client.get("/api/reports/quarterly").json()
        quarters = [q["quarter"] for q in data]
        assert quarters == sorted(quarters)

    def test_quarterly_reports_match_orders(self, client):
        """Test that quarterly totals add up to the raw orders data."""
        orders = client.get("/api/orders").json()
        data = client.get("/api/reports/quarterly").json()

        assert sum(q["total_orders"] for q in data) == len(orders)
        assert abs(sum(q["total_revenue"] for q in data) - sum(o["total_value"] for o in orders)) < 0.01

    def test_quarterly_reports_calculations(self, client):
        """Test average order value and fulfillment rate calculations."""
        data = client.get("/api/reports/quarterly").json()

        for q in data:
            assert abs(q["avg_order_value"] - q["total_revenue"] / q["total_orders"]) < 0.01
            expected_rate = q["delivered_orders"] / q["total_orders"] * 100
            assert abs(q["fulfillment_rate"] - expected_rate) < 0.1
            assert 0 <= q["fulfillment_rate"] <= 100

    def test_quarterly_reports_revenue_rounded(self, client):
        """Test that revenue has no floating point noise beyond 2 decimals."""
        data = client.get("/api/reports/quarterly").json()

        for q in data:
            assert q["total_revenue"] == round(q["total_revenue"], 2)

    def test_quarterly_reports_by_warehouse(self, client):
        """Test that the warehouse filter limits the aggregated orders."""
        orders = client.get("/api/orders?warehouse=Tokyo").json()
        data = client.get("/api/reports/quarterly?warehouse=Tokyo").json()

        assert sum(q["total_orders"] for q in data) == len(orders)

    def test_quarterly_reports_by_category(self, client):
        """Test that the category filter limits the aggregated orders."""
        orders = client.get("/api/orders?category=Sensors").json()
        data = client.get("/api/reports/quarterly?category=Sensors").json()

        assert sum(q["total_orders"] for q in data) == len(orders)

    def test_quarterly_reports_by_status(self, client):
        """Test that filtering by Delivered yields a 100% fulfillment rate."""
        data = client.get("/api/reports/quarterly?status=Delivered").json()

        assert len(data) > 0
        for q in data:
            assert q["fulfillment_rate"] == 100

    def test_quarterly_reports_by_quarter(self, client):
        """Test that a quarter filter only returns that quarter."""
        data = client.get("/api/reports/quarterly?month=Q2-2025").json()

        assert len(data) == 1
        assert data[0]["quarter"] == "Q2-2025"

    def test_quarterly_reports_by_month(self, client):
        """Test that a single-month filter only returns the quarter containing it."""
        data = client.get("/api/reports/quarterly?month=2025-02").json()

        assert len(data) == 1
        assert data[0]["quarter"] == "Q1-2025"

    def test_quarterly_reports_multiple_filters(self, client):
        """Test combining several filters."""
        orders = client.get(
            "/api/orders?warehouse=London&category=Sensors&status=Delivered&month=Q3-2025"
        ).json()
        data = client.get(
            "/api/reports/quarterly?warehouse=London&category=Sensors&status=Delivered&month=Q3-2025"
        ).json()

        assert sum(q["total_orders"] for q in data) == len(orders)

    def test_quarterly_reports_all_filters_equal_unfiltered(self, client):
        """Test that 'all' behaves the same as no filter."""
        unfiltered = client.get("/api/reports/quarterly").json()
        all_filters = client.get(
            "/api/reports/quarterly?warehouse=all&category=all&status=all&month=all"
        ).json()

        assert unfiltered == all_filters

    def test_quarterly_reports_no_matches(self, client):
        """Test that filters matching nothing return an empty list, not an error."""
        response = client.get("/api/reports/quarterly?warehouse=Nowhere")
        assert response.status_code == 200
        assert response.json() == []


class TestMonthlyTrendsEndpoint:
    """Test suite for /api/reports/monthly-trends."""

    def test_get_monthly_trends(self, client):
        """Test getting monthly trends without filters."""
        response = client.get("/api/reports/monthly-trends")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        for month in data:
            assert "month" in month
            assert "order_count" in month
            assert "revenue" in month
            assert "delivered_count" in month

    def test_monthly_trends_sorted_and_format(self, client):
        """Test months are YYYY-MM strings in chronological order."""
        data = client.get("/api/reports/monthly-trends").json()
        months = [m["month"] for m in data]

        assert months == sorted(months)
        for m in months:
            assert len(m) == 7 and m[4] == "-"

    def test_monthly_trends_match_orders(self, client):
        """Test that monthly totals add up to the raw orders data."""
        orders = client.get("/api/orders").json()
        data = client.get("/api/reports/monthly-trends").json()

        assert sum(m["order_count"] for m in data) == len(orders)
        assert abs(sum(m["revenue"] for m in data) - sum(o["total_value"] for o in orders)) < 0.01

    def test_monthly_trends_revenue_rounded(self, client):
        """Test that revenue has no floating point noise beyond 2 decimals."""
        data = client.get("/api/reports/monthly-trends").json()

        for m in data:
            assert m["revenue"] == round(m["revenue"], 2)

    def test_monthly_trends_by_warehouse(self, client):
        """Test that the warehouse filter limits the aggregated orders."""
        orders = client.get("/api/orders?warehouse=Tokyo").json()
        data = client.get("/api/reports/monthly-trends?warehouse=Tokyo").json()

        assert sum(m["order_count"] for m in data) == len(orders)

    def test_monthly_trends_by_category(self, client):
        """Test that the category filter limits the aggregated orders."""
        orders = client.get("/api/orders?category=Actuators").json()
        data = client.get("/api/reports/monthly-trends?category=Actuators").json()

        assert sum(m["order_count"] for m in data) == len(orders)

    def test_monthly_trends_by_status(self, client):
        """Test that filtering by Delivered means every order counts as delivered."""
        data = client.get("/api/reports/monthly-trends?status=Delivered").json()

        assert len(data) > 0
        for m in data:
            assert m["delivered_count"] == m["order_count"]

    def test_monthly_trends_by_quarter(self, client):
        """Test that a quarter filter only returns that quarter's months."""
        data = client.get("/api/reports/monthly-trends?month=Q1-2025").json()

        assert len(data) > 0
        assert {m["month"] for m in data} <= {"2025-01", "2025-02", "2025-03"}

    def test_monthly_trends_by_month(self, client):
        """Test that a single-month filter returns just that month."""
        data = client.get("/api/reports/monthly-trends?month=2025-05").json()

        assert len(data) == 1
        assert data[0]["month"] == "2025-05"

    def test_monthly_trends_no_matches(self, client):
        """Test that filters matching nothing return an empty list, not an error."""
        response = client.get("/api/reports/monthly-trends?category=Nothing")
        assert response.status_code == 200
        assert response.json() == []

    def test_quarterly_and_monthly_consistent(self, client):
        """Test that both endpoints agree on totals under the same filters."""
        query = "?warehouse=San Francisco&status=Shipped"
        quarterly = client.get(f"/api/reports/quarterly{query}").json()
        monthly = client.get(f"/api/reports/monthly-trends{query}").json()

        assert sum(q["total_orders"] for q in quarterly) == sum(m["order_count"] for m in monthly)
        assert abs(sum(q["total_revenue"] for q in quarterly) - sum(m["revenue"] for m in monthly)) < 0.01
