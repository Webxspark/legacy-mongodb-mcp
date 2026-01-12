// 01-init.js
// access the testdb database
var db = db.getSiblingDB('testdb');

// Create a users collection with some sample data
db.createCollection('users');
db.users.insert([
  {
    "username": "jdoe",
    "email": "jdoe@example.com",
    "roles": ["admin", "editor"],
    "created_at": new Date("2015-01-01T00:00:00Z"),
    "legacy_id": 1001,
    "details": {
        "age": 30,
        "active": true
    }
  },
  {
    "username": "asmith",
    "email": "asmith@example.com",
    "roles": ["viewer"],
    "created_at": new Date("2016-05-23T10:30:00Z"),
    "legacy_id": 1002,
    "details": {
        "age": 25,
        "active": true
    }
  },
  {
    "username": "bwayne",
    "email": "batman@gotham.city",
    "roles": ["hero"],
    "created_at": new Date("2010-09-15T20:15:00Z"),
    "legacy_id": 1003,
    "details": {
        "age": 35,
        "active": false
    }
  }
]);

// Create a products collection
db.createCollection('products');
db.products.insert([
    { "_id": 1, "name": "Legacy Widget A", "price": 19.99, "stock": 100, "category": "widgets" },
    { "_id": 2, "name": "Legacy Widget B", "price": 29.99, "stock": 0, "category": "widgets" },
    { "_id": 3, "name": "Gadget X", "price": 9.99, "stock": 500, "category": "gadgets" }
]);

// Create a logs collection for some timeseries-like data
db.createCollection('system_logs');
for (var i = 0; i < 50; i++) {
    db.system_logs.insert({
        "level": i % 3 === 0 ? "INFO" : (i % 3 === 1 ? "WARN" : "ERROR"),
        "message": "System event number " + i,
        "timestamp": new Date(new Date().getTime() - (i * 1000 * 60 * 60)), // Go back in time
        "metadata": {
            "node": "server-" + (i % 5)
        }
    });
}

print("Legacy MongoDB migration data initialized in 'testdb'");
