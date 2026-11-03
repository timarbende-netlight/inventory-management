"""
Tests for restocking API endpoints.
"""
import pytest

import mock_data


@pytest.fixture(autouse=True)
def clear_restock_orders():
    """Restock orders live in memory; clear them so tests stay independent.

    main.py imports the same list object, so it must be cleared in place, not rebound.
    """
    mock_data.restock_orders.clear()
    yield
    mock_data.restock_orders.clear()


class TestRestockingEndpoints:
    """Test suite for restocking catalog and order endpoints."""

    def test_get_restocking_catalog(self, client):
        """Test that the catalog joins forecasts with cost and lead time."""
        response = client.get("/api/restocking/catalog")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        for item in data:
            assert "item_sku" in item
            assert "item_name" in item
            assert "forecasted_demand" in item
            assert "trend" in item
            assert "supplier" in item
            assert isinstance(item["unit_cost"], (int, float))
            assert item["unit_cost"] > 0
            assert isinstance(item["lead_time_days"], int)
            assert item["lead_time_days"] > 0
            assert isinstance(item["quantity_on_hand"], int)
            assert item["quantity_on_hand"] >= 0

    def test_catalog_covers_all_forecasts(self, client):
        """Test that every demand forecast SKU can be priced."""
        forecasts = client.get("/api/demand").json()
        catalog = client.get("/api/restocking/catalog").json()

        assert {f["item_sku"] for f in forecasts} == {c["item_sku"] for c in catalog}

    def test_create_restock_order(self, client):
        """Test submitting a valid order: server-computed total and lead time."""
        catalog = client.get("/api/restocking/catalog").json()
        a, b = catalog[0], catalog[1]

        payload = {
            "budget": 1_000_000,
            "items": [
                {"item_sku": a["item_sku"], "quantity": 10},
                {"item_sku": b["item_sku"], "quantity": 5},
            ],
        }
        response = client.post("/api/restocking/orders", json=payload)
        assert response.status_code == 201

        order = response.json()
        expected_total = 10 * a["unit_cost"] + 5 * b["unit_cost"]
        assert abs(order["total_cost"] - expected_total) < 0.01
        # Order is complete when the slowest line arrives
        assert order["lead_time_days"] == max(a["lead_time_days"], b["lead_time_days"])
        assert order["order_number"].startswith("RST-")
        assert order["status"] == "Submitted"
        assert len(order["items"]) == 2
        assert "expected_delivery" in order

    def test_create_order_ignores_client_prices(self, client):
        """Test that extra client-supplied price fields cannot change the total."""
        catalog = client.get("/api/restocking/catalog").json()
        item = catalog[0]

        payload = {
            "budget": 1_000_000,
            "items": [{"item_sku": item["item_sku"], "quantity": 2, "unit_cost": 0.01}],
        }
        response = client.post("/api/restocking/orders", json=payload)
        assert response.status_code == 201
        assert abs(response.json()["total_cost"] - 2 * item["unit_cost"]) < 0.01

    def test_create_order_over_budget(self, client):
        """Test that an order exceeding the budget is rejected."""
        item = client.get("/api/restocking/catalog").json()[0]
        payload = {
            "budget": 1,
            "items": [{"item_sku": item["item_sku"], "quantity": 100}],
        }
        response = client.post("/api/restocking/orders", json=payload)
        assert response.status_code == 400
        assert "budget" in response.json()["detail"].lower()

    def test_create_order_unknown_sku(self, client):
        """Test that an unknown SKU is rejected."""
        payload = {"budget": 1000, "items": [{"item_sku": "NOPE-999", "quantity": 1}]}
        response = client.post("/api/restocking/orders", json=payload)
        assert response.status_code == 400

    def test_create_order_non_positive_quantity(self, client):
        """Test that zero and negative quantities are rejected."""
        item = client.get("/api/restocking/catalog").json()[0]
        for qty in (0, -3):
            payload = {"budget": 1000, "items": [{"item_sku": item["item_sku"], "quantity": qty}]}
            response = client.post("/api/restocking/orders", json=payload)
            assert response.status_code == 400

    def test_create_order_empty_items(self, client):
        """Test that an order with no items is rejected."""
        response = client.post("/api/restocking/orders", json={"budget": 1000, "items": []})
        assert response.status_code == 400

    def test_create_order_duplicate_sku(self, client):
        """Test that the same SKU cannot appear twice in one order."""
        item = client.get("/api/restocking/catalog").json()[0]
        line = {"item_sku": item["item_sku"], "quantity": 1}
        response = client.post("/api/restocking/orders", json={"budget": 1_000_000, "items": [line, line]})
        assert response.status_code == 400

    def test_create_order_missing_fields(self, client):
        """Test that a malformed body fails validation."""
        response = client.post("/api/restocking/orders", json={"items": []})
        assert response.status_code == 422

    def test_get_restock_orders_newest_first(self, client):
        """Test that submitted orders are listed newest first."""
        assert client.get("/api/restocking/orders").json() == []

        item = client.get("/api/restocking/catalog").json()[0]
        for qty in (1, 2):
            client.post(
                "/api/restocking/orders",
                json={"budget": 1_000_000, "items": [{"item_sku": item["item_sku"], "quantity": qty}]},
            )

        orders = client.get("/api/restocking/orders").json()
        assert len(orders) == 2
        assert orders[0]["items"][0]["quantity"] == 2
        assert orders[0]["order_number"] != orders[1]["order_number"]
